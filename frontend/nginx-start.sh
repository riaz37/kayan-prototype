#!/bin/sh
PORT=${PORT:-3000}

cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen ${PORT};
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

exec nginx -g "daemon off;"
