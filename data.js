// AUTO-GENERATED — do not edit by hand.
// Run: python3 scripts/sync_stats.py  OR  trigger the GitHub Action "Sync Stats from Sheet"
// Last synced: (manual seed)

const T={m:14,gf:48,ga:33,gd:15,w:7,d:4,l:3,form:["D","L","W","W","L"]};
T.pts=T.w*3+T.d; T.ppg=T.pts/T.m;

const M=[
  {wk:1,dt:"04/01",vs:"Thiết Bị Việt FC",gf:4,ga:2,r:"W",v:"Etihad Q12"},
  {wk:2,dt:"11/01",vs:"Long Xuyên FC",gf:4,ga:2,r:"W",v:"Giga Arena"},
  {wk:3,dt:"18/01",vs:"Vườn Mai Phương Bình FC",gf:0,ga:2,r:"L",v:"Giga Arena"},
  {wk:4,dt:"25/01",vs:"Long Xuyên FC",gf:2,ga:0,r:"W",v:"Giga Arena"},
  {wk:9,dt:"01/03",vs:"Liên Quân FC",gf:3,ga:1,r:"W",v:"Etihad Q12"},
  {wk:10,dt:"08/03",vs:"Sân Cáp",gf:3,ga:3,r:"D",v:"Giga Arena"},
  {wk:11,dt:"15/03",vs:"Long Xuyên FC",gf:3,ga:3,r:"D",v:"Giga Arena"},
  {wk:12,dt:"22/03",vs:"Friends FC",gf:3,ga:3,r:"D",v:"Etihad Q12"},
  {wk:14,dt:"05/04",vs:"Nhật Huy FC",gf:5,ga:2,r:"W",v:"Giga Arena"},
  {wk:15,dt:"12/04",vs:"Huyền Thoại FC",gf:4,ga:4,r:"D",v:"Lotus Tân Sơn"},
  {wk:16,dt:"19/04",vs:"ĐH TDTT",gf:3,ga:4,r:"L",v:"ĐH TDTT"},
  {wk:19,dt:"10/05",vs:"Sân Cáp",gf:5,ga:3,r:"W",v:"ĐH TDTT"},
  {wk:20,dt:"17/05",vs:"Lên Bia FC",gf:8,ga:2,r:"W",v:"Dĩ An"},
  {wk:21,dt:"24/05",vs:"AE Bình Định",gf:1,ga:2,r:"L",v:"Giga Arena"},
];

// s=scored [{sc,as,t:"normal"|"pen",h:1|2}]  ms=missed pen  c=conceded [{gk,h}]  pf/ps=pen faced/saved
const MG={
  21:{s:[{sc:"Văn Chung",as:"Văn Quang",t:"normal",h:1}],c:[{gk:"Đức Khoa",h:1},{gk:"Đức Khoa",h:2}],pf:0,ps:0},
};

// GK aggregate from sheet (fallback when per-match detail is missing)
const GKD_SHEET={
  "Đức Khoa":{h1:1,h2:1,pf:0,ps:0},
};

// Compute aggregates from goal detail
const AST_H={},PEN={},HGF={h1:0,h2:0},HGA={h1:0,h2:0},GKD={};
Object.values(MG).forEach(mg=>{
  (mg.s||[]).forEach(g=>{
    if(g.as){if(!AST_H[g.as])AST_H[g.as]={h1:0,h2:0};g.h===1?AST_H[g.as].h1++:AST_H[g.as].h2++;}
    if(g.t==="pen"){if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].sc++}
    g.h===1?HGF.h1++:HGF.h2++;
  });
  (mg.ms||[]).forEach(g=>{if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].ms++});
  (mg.c||[]).forEach(c=>{
    if(!GKD[c.gk])GKD[c.gk]={conc:0,h1:0,h2:0,pf:0,ps:0};
    GKD[c.gk].conc++;c.h===1?(GKD[c.gk].h1++,HGA.h1++):(GKD[c.gk].h2++,HGA.h2++);
  });
  if(mg.pf)Object.values(GKD).forEach(d=>{d.pf+=mg.pf;d.ps+=mg.ps||0});
});
// Supplement with sheet GK totals for any GK not yet in per-match detail
Object.entries(GKD_SHEET).forEach(([k,v])=>{
  if(!GKD[k]){GKD[k]={conc:v.h1+v.h2,h1:v.h1,h2:v.h2,pf:v.pf,ps:v.ps};HGA.h1+=v.h1;HGA.h2+=v.h2;}
});
const AST=Object.fromEntries(Object.entries(AST_H).map(([k,v])=>[k,v.h1+v.h2]));

const P=[
  {n:"Mai Cồ Hiếu",p:"LW",no:"23",g:3,m:14,mp:1,wp:.5,fa:["D","L","W","W","L"],w:7,d:4,l:3,gf:48,ga:33,gd:15,t:"main"},
  {n:"Văn Quang",p:"RW",no:"10",g:1,m:10,mp:.71,wp:.6,fa:["D","N","N","W","L"],w:6,d:2,l:2,gf:34,ga:20,gd:14,t:"main"},
  {n:"Nguyên Khôi",p:"RB",no:"19",g:0,m:9,mp:.64,wp:.556,fa:["N","N","W","W","L"],w:5,d:2,l:2,gf:30,ga:19,gd:11,t:"main"},
  {n:"Lucky Trần",p:"CM",no:"11",g:0,m:11,mp:.79,wp:.545,fa:["N","L","N","W","L"],w:6,d:3,l:2,gf:39,ga:24,gd:15,t:"main"},
  {n:"Quốc Long",p:"CM",no:"8",g:4,m:11,mp:.79,wp:.545,fa:["D","L","N","W","L"],w:6,d:2,l:3,gf:37,ga:24,gd:13,t:"main"},
  {n:"Hữu Duyên",p:"CB",no:"47",g:1,m:13,mp:.93,wp:.462,fa:["D","L","W","W","L"],w:6,d:4,l:3,gf:43,ga:31,gd:12,t:"main"},
  {n:"Nguyễn Hoàng",p:"LB",no:"39",g:0,m:12,mp:.86,wp:.583,fa:["D","N","W","W","L"],w:7,d:3,l:2,gf:42,ga:26,gd:16,t:"main"},
  {n:"Văn Tới",p:"GK",no:"16",g:0,m:3,mp:.21,wp:.667,fa:["N","N","W","W","N"],w:2,d:1,l:0,gf:16,ga:8,gd:8,t:"main"},
  {n:"Đức Khoa",p:"GK",no:"01",g:0,m:11,mp:.79,wp:.455,fa:["D","L","N","N","L"],w:5,d:3,l:3,gf:32,ga:25,gd:7,t:"main"},
  {n:"D.Chí Hoàng",p:"CB",no:"24",g:0,m:9,mp:.64,wp:.444,fa:["D","L","W","N","L"],w:4,d:3,l:2,gf:29,ga:23,gd:6,t:"main"},
  {n:"Minh Hoàng",p:"LB",no:"12",g:0,m:9,mp:.64,wp:.556,fa:["N","N","W","W","L"],w:5,d:2,l:2,gf:33,ga:21,gd:12,t:"main"},
  {n:"Trung Nguyên",p:"CM",no:"14",g:2,m:13,mp:.93,wp:.462,fa:["D","L","W","W","L"],w:6,d:4,l:3,gf:44,ga:31,gd:13,t:"main"},
  {n:"Tài Ba",p:"CB",no:"3",g:1,m:12,mp:.86,wp:.417,fa:["D","L","N","W","L"],w:5,d:4,l:3,gf:39,ga:28,gd:11,t:"main"},
  {n:"Văn Chung",p:"ST",no:"9",g:8,m:9,mp:.64,wp:.444,fa:["D","L","W","N","L"],w:4,d:2,l:3,gf:28,ga:23,gd:5,t:"main"},
  {n:"Gia Lộc",p:"LM",no:"75",g:2,m:10,mp:.71,wp:.5,fa:["D","L","W","W","L"],w:5,d:2,l:3,gf:33,ga:23,gd:10,t:"main"},
  {n:"Phú Bình",p:"CB",no:"15",g:0,m:4,mp:.29,wp:.5,fa:["N","L","N","N","N"],w:2,d:1,l:1,gf:11,ga:8,gd:3,t:"main"},
  {n:"Khâm",p:"RW",no:"22",g:7,m:10,mp:.71,wp:.5,fa:["N","L","W","W","L"],w:5,d:2,l:3,gf:32,ga:22,gd:10,t:"main"},
  {n:"Cảm",p:"LW",no:"7",g:13,m:12,mp:.86,wp:.417,fa:["D","L","W","W","L"],w:5,d:4,l:3,gf:41,ga:30,gd:11,t:"main"},
  {n:"Hoàng Đại",p:"ST",no:"17",g:1,m:3,mp:.21,wp:.333,fa:["D","N","N","W","N"],w:1,d:2,l:0,gf:15,ga:9,gd:6,t:"main"},
  {n:"Lâm",p:"CM",no:"6",g:3,m:6,mp:.43,wp:.5,fa:["D","L","W","W","N"],w:3,d:2,l:1,gf:28,ga:18,gd:10,t:"main"},
  {n:"Hữu Nghĩa",p:"LB",no:"5",g:0,m:3,mp:.21,wp:.667,fa:["N","N","W","W","L"],w:2,d:0,l:1,gf:14,ga:7,gd:7,t:"sub"},
  {n:"Anh Sơn",p:"MF",no:"",g:0,m:3,mp:.21,wp:.333,fa:["D","N","N","N","N"],w:1,d:2,l:0,gf:11,ga:9,gd:2,t:"sub"},
  {n:"Chí Quỹ",p:"MF",no:"4",g:0,m:2,mp:.14,wp:.5,fa:["N","N","N","N","N"],w:1,d:1,l:0,gf:7,ga:5,gd:2,t:"sub"},
  {n:"Tiến",p:"DF",no:"",g:0,m:3,mp:.21,wp:.333,fa:["D","N","N","W","N"],w:1,d:2,l:0,gf:15,ga:9,gd:6,t:"sub"},
  {n:"Mới",p:"MF",no:"",g:1,m:2,mp:.14,wp:.5,fa:["D","N","N","N","N"],w:1,d:1,l:0,gf:9,ga:6,gd:3,t:"sub"},
];

const PM={"Mai Cồ Hiếu":[0,0,0,1,0,0,0,0,0,0,0,0,2,0],"Văn Quang":[1,0,0,0,0,null,0,null,0,0,null,null,0,0],"Nguyên Khôi":[0,0,0,0,null,0,null,0,null,null,null,0,0,0],"Lucky Trần":[0,0,null,0,0,0,0,0,0,null,0,null,0,0],"Quốc Long":[1,0,0,1,0,null,0,null,0,0,2,null,0,0],"Hữu Duyên":[0,0,0,0,1,0,0,0,null,0,0,0,0,0],"Nguyễn Hoàng":[0,0,0,0,0,null,0,0,0,0,null,0,0,0],"Văn Tới":[null,null,null,null,null,null,0,null,null,null,null,0,0,null],
  "Đức Khoa":[0,0,0,0,0,0,null,0,0,0,0,null,null,0],"D.Chí Hoàng":[0,0,null,0,null,0,null,0,null,0,0,0,null,0],"Minh Hoàng":[0,0,0,null,null,null,0,0,0,null,null,0,0,0],"Trung Nguyên":[null,1,0,0,0,0,0,0,0,1,0,0,0,0],"Tài Ba":[null,0,0,0,0,0,0,1,0,0,0,null,0,0],"Hữu Nghĩa":[null,null,null,null,null,null,null,null,null,null,null,0,0,0],"Văn Chung":[1,null,0,null,1,2,null,null,0,0,1,2,null,1],"Gia Lộc":[1,null,0,0,0,null,null,0,null,null,1,null,0,0],"Phú Bình":[null,null,null,0,0,null,0,null,null,null,0,null,null,null],"Khâm":[null,2,0,0,1,1,2,null,null,null,0,0,1,0],"Cảm":[null,1,0,0,null,0,1,2,3,1,0,2,3,0],"Hoàng Đại":[null,null,null,null,null,null,null,0,null,0,null,null,1,null],"Lâm":[null,null,null,null,null,null,null,0,1,1,0,0,1,null],"Anh Sơn":[0,null,null,null,null,0,null,null,null,0,null,null,null,null],"Chí Quỹ":[null,0,null,null,null,null,0,null,null,null,null,null,null,null],"Tiến":[null,null,null,null,null,null,null,0,null,0,null,null,0,null],"Mới":[null,null,null,null,null,null,null,null,1,0,null,null,null,null]};
