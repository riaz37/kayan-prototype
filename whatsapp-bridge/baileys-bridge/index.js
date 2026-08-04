/**
 * WhatsApp Bridge - Baileys
 * Connects WhatsApp Web to Kayan AI Agent
 */

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, makeCacheableSignalKeyStore } = require('@whiskeysockets/baileys');
const pino = require('pino');
const http = require('http');
const fs = require('fs');
const path = require('path');
const QRCode = require('qrcode');

// Configuration
const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8000';
const SESSION_DIR = path.join(__dirname, 'session');
const QR_IMAGE_PATH = path.join(__dirname, 'whatsapp_qr.png');

// Ensure session directory exists
if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
}

// Logger
const logger = pino({ level: 'warn' });

// Store connected socket
let sock = null;

/**
 * Send message to LLM agent
 */
async function sendToAgent(phone, message) {
    return new Promise((resolve, reject) => {
        const payload = JSON.stringify({
            object: "whatsapp_business_account",
            entry: [{
                changes: [{
                    value: {
                        messaging_product: "whatsapp",
                        metadata: {
                            display_phone_number: "whatsapp",
                            phone_number_id: "baileys"
                        },
                        contacts: [{
                            wa_id: phone,
                            profile: { name: "WhatsApp User" }
                        }],
                        messages: [{
                            from: phone,
                            id: `wamid.${Date.now()}`,
                            timestamp: Math.floor(Date.now() / 1000).toString(),
                            type: "text",
                            text: { body: message }
                        }]
                    },
                    field: "messages"
                }]
            }]
        });

        const url = new URL(AGENT_URL);
        const options = {
            hostname: url.hostname,
            port: url.port || 80,
            path: '/webhook',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(payload)
            }
        };

        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                console.log(`✅ Agent notified for ${phone} (status: ${res.statusCode})`);
                resolve(res.statusCode);
            });
        });

        req.on('error', (e) => {
            console.error(`❌ Error sending to agent: ${e.message}`);
            reject(e);
        });

        req.write(payload);
        req.end();
    });
}

/**
 * Send message via Baileys
 */
async function sendMessage(phone, text) {
    if (!sock) {
        console.error('❌ Not connected to WhatsApp');
        return false;
    }
    try {
        const jid = phone.includes('@') ? phone : `${phone}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        console.log(`✅ Sent to ${phone}: ${text.substring(0, 50)}...`);
        return true;
    } catch (e) {
        console.error(`❌ Failed to send to ${phone}: ${e.message}`);
        return false;
    }
}

/**
 * Send typing indicator (presence update)
 */
async function sendTypingIndicator(phone) {
    if (!sock) {
        console.error('❌ Not connected to WhatsApp');
        return false;
    }
    try {
        const jid = phone.includes('@') ? phone : `${phone}@s.whatsapp.net`;
        await sock.sendPresenceUpdate('composing', jid);
        console.log(`⌨️ Typing indicator sent to ${phone}`);
        return true;
    } catch (e) {
        console.error(`❌ Failed to send typing indicator to ${phone}: ${e.message}`);
        return false;
    }
}

/**
 * Stop typing indicator
 */
async function stopTypingIndicator(phone) {
    if (!sock) {
        return false;
    }
    try {
        const jid = phone.includes('@') ? phone : `${phone}@s.whatsapp.net`;
        await sock.sendPresenceUpdate('paused', jid);
        return true;
    } catch (e) {
        return false;
    }
}

/**
 * Handle incoming messages
 */
function handleMessages(messages) {
    for (const msg of messages) {
        // Skip if not a direct message
        if (msg.key.remoteJid.endsWith('@g.us')) {
            continue;
        }

        const phone = msg.key.remoteJid.replace('@s.whatsapp.net', '');
        const text = msg.message?.conversation || 
                    msg.message?.extendedTextMessage?.text || 
                    null;

        if (text) {
            console.log(`\n📱 Message from ${phone}: ${text}`);
            sendToAgent(phone, text).catch(console.error);
        }
    }
}

/**
 * HTTP Server for outbound messages from agent
 */
const httpServer = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/send') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { phone, text } = JSON.parse(body);
                if (!phone || !text) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'phone and text required' }));
                    return;
                }
                const ok = await sendMessage(phone, text);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ ok }));
            } catch (e) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: e.message }));
            }
        });
    } else if (req.method === 'POST' && req.url === '/typing') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { phone, typing } = JSON.parse(body);
                if (!phone) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'phone required' }));
                    return;
                }
                const ok = typing !== false 
                    ? await sendTypingIndicator(phone) 
                    : await stopTypingIndicator(phone);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ ok }));
            } catch (e) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: e.message }));
            }
        });
    } else if (req.method === 'GET' && req.url === '/status') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ connected: !!sock }));
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

const BRIDGE_PORT = process.env.BRIDGE_PORT || 8002;
httpServer.listen(BRIDGE_PORT, () => {
    console.log(`🌐 Bridge HTTP server on port ${BRIDGE_PORT}`);
    console.log('   POST /send  — send message {phone, text}');
    console.log('   GET  /status — check connection\n');
});

/**
 * Start WhatsApp connection
 */
async function startBot() {
    console.log('🚀 Starting WhatsApp Bridge...');
    console.log(`📡 Agent URL: ${AGENT_URL}`);
    console.log(`📁 Session: ${SESSION_DIR}\n`);

    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

    sock = makeWASocket({
        logger,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger)
        },
        printQRInTerminal: false,
        browser: ['Kayan AI Agent', 'Chrome', '1.0.0']
    });

    // Handle credentials update
    sock.ev.on('creds.update', saveCreds);

    // Handle connection updates
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n📱 QR Code generated!');
            console.log('Saving QR code to: whatsapp_qr.png\n');
            
            // Save QR code as image
            await QRCode.toFile(QR_IMAGE_PATH, qr, {
                width: 400,
                margin: 2,
                color: {
                    dark: '#000000',
                    light: '#FFFFFF'
                }
            });
            
            console.log('✅ QR code saved!');
            console.log('👉 Open whatsapp_qr.png and scan with WhatsApp\n');
            
            // Also open the image automatically
            const { exec } = require('child_process');
            exec(`open ${QR_IMAGE_PATH}`);
        }

        if (connection === 'close') {
            const reason = lastDisconnect?.error?.output?.statusCode;
            console.log(`\n⚠️ Connection closed. Reason: ${reason}`);

            if (reason === DisconnectReason.loggedOut) {
                console.log('❌ Logged out. Please restart and scan QR again.');
                fs.rmSync(SESSION_DIR, { recursive: true, force: true });
                process.exit(1);
            } else {
                console.log('🔄 Reconnecting...');
                startBot();
            }
        }

        if (connection === 'open') {
            console.log('\n✅ Connected to WhatsApp!');
            console.log('   Waiting for messages...\n');
            
            // Delete QR image after successful connection
            if (fs.existsSync(QR_IMAGE_PATH)) {
                fs.unlinkSync(QR_IMAGE_PATH);
            }
        }
    });

    // Handle incoming messages
    sock.ev.on('messages.upsert', (m) => {
        if (m.type === 'notify') {
            handleMessages(m.messages);
        }
    });
}

// Start the bot
startBot().catch((err) => {
    console.error('❌ Failed to start bot:', err);
    process.exit(1);
});
