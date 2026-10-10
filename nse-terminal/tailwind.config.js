export default {
  content:['./index.html','./src/**/*.{js,jsx}'],
  theme:{extend:{
    colors:{bg:'#0b0e14',card:'#121620',up:'#10b981',down:'#ef4444'},
    borderColor:{DEFAULT:'rgba(255,255,255,0.08)'},
    fontFamily:{mono:['"JetBrains Mono"','"Fira Code"','monospace'],sans:['Inter','system-ui','sans-serif']},
    keyframes:{sheet:{from:{transform:'translateY(100%)'},to:{transform:'none'}},fade:{from:{opacity:0,transform:'translateY(4px)'},to:{opacity:1,transform:'none'}}},
    animation:{sheet:'sheet .28s cubic-bezier(.32,.72,0,1)',fade:'fade .2s ease-out'}
  }}}
