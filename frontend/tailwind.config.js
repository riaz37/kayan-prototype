module.exports = {
  content: ["./index.html", "./js/**/*.jsx", "./dist/**/*.js"],
  theme: {
    extend: {
      fontFamily: { sans: ['"IBM Plex Sans Arabic"','"Noto Sans Arabic"','"Segoe UI"','Tahoma','ui-sans-serif','system-ui','sans-serif'] },
      colors: {
        canvas: '#FAFAFB',
        ink:  { DEFAULT:'#0F172A', muted:'#64748B', soft:'#94A3B8' },
        line: { DEFAULT:'#EAECF0', soft:'#F2F4F7' },
        brand:{ 50:'#F0FBF9',100:'#D7F4EF',200:'#AEE9E1',300:'#7AD7CC',400:'#45BCB0',
                500:'#1BA093',600:'#0F8478',700:'#0D6A61',800:'#0E544E',900:'#0F4642' },
      },
      borderRadius: { xl:'0.875rem', '2xl':'1.125rem' },
      boxShadow: {
        card:'0 1px 2px 0 rgb(16 24 40 / 0.04), 0 1px 3px 0 rgb(16 24 40 / 0.04)',
        pop: '0 8px 24px -6px rgb(16 24 40 / 0.10), 0 2px 6px -2px rgb(16 24 40 / 0.05)',
      },
      keyframes: { in:{ '0%':{opacity:'0',transform:'translateY(4px)'},'100%':{opacity:'1',transform:'none'} } },
      animation: { in:'in .28s cubic-bezier(.16,1,.3,1) both' },
    }
  },
  plugins: [],
}
