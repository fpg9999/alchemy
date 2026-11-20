import sys, math, numpy as np
sys.path.insert(0,'.'); sys.path.insert(0,'examples')
import rigid_dead as RD
from PIL import Image
BETA=0.3; RMAX=2.5
def pf(dn):
    out=np.zeros_like(dn); m=dn<BETA; out[m]=dn[m]/BETA-1.0
    m2=(dn>=BETA)&(dn<1.0); out[m2]=1.0-np.abs(2*dn[m2]-1-BETA)/(1-BETA); return out
class Live(RD.RigidWorld):
    def __init__(self, n, w=40.0, h=30.0, r=0.5, seed=1, ntypes=6, g=0.0):
        super().__init__(n, w, h, r, seed, g)
        rng=np.random.default_rng(seed+99)
        self.k=rng.uniform(-1,1,(ntypes,ntypes))
        self.t=rng.integers(0,ntypes,n)
    def mol_force(self):
        cell=RMAX
        ci=np.floor(self.pos/cell).astype(np.int64)
        ch=int(self.h/cell)+2
        key=ci[:,0]*ch+ci[:,1]
        order=np.argsort(key, kind="stable"); sk=key[order]
        n=self.n; base=np.arange(n); los=[]; cnts=[]
        for ox in (-1,0,1):
            for oy in (-1,0,1):
                nk=key+ox*ch+oy
                lo=np.searchsorted(sk,nk,"left"); hi=np.searchsorted(sk,nk,"right")
                los.append(lo); cnts.append(hi-lo)
        los=np.concatenate(los); cnts=np.concatenate(cnts)
        tot=int(cnts.sum())
        if tot==0: return np.zeros(n), np.zeros(n)
        starts=np.repeat(los,cnts)
        offs=np.arange(tot)-np.repeat(np.cumsum(cnts)-cnts,cnts)
        jj=order[starts+offs]; ii=np.repeat(np.tile(base,9),cnts)
        m=ii!=jj; ii,jj=ii[m],jj[m]
        d=self.pos[jj]-self.pos[ii]; dist=np.hypot(d[:,0],d[:,1])
        keep=(dist<RMAX)&(dist>1e-9)
        ii,jj,d,dist=ii[keep],jj[keep],d[keep],dist[keep]
        f=pf(dist/RMAX)*self.k[self.t[ii],self.t[jj]]
        fx=np.zeros(n); fy=np.zeros(n)
        np.add.at(fx,ii,f*d[:,0]/dist); np.add.at(fy,ii,f*d[:,1]/dist)
        return fx,fy
    def step(self):
        fx,fy=self.mol_force()
        self.vel[:,0]+=fx*self.dt; self.vel[:,1]+=fy*self.dt
        self.vel[:,1]+=self.g*self.dt
        self.vel*=self.damp
        self.pos+=self.vel*self.dt
        self.pos[:,0]=np.clip(self.pos[:,0],self.r,self.w-self.r)
        self.pos[:,1]=np.clip(self.pos[:,1],self.r,self.h-self.r)
        dmin=2*self.r
        for _ in range(self.iters):
            ii,jj,dx,dy,dist=self.neighbors()
            if not len(ii): break
            ov=dmin-dist; hit=ov>0
            if not hit.any(): break
            ii,jj=ii[hit],jj[hit]; ov,dx,dy,dist=ov[hit],dx[hit],dy[hit],dist[hit]
            ux,uy=dx/dist,dy/dist; push=ov*0.5
            np.add.at(self.pos,(ii,0),-ux*push); np.add.at(self.pos,(ii,1),-uy*push)
            np.add.at(self.pos,(jj,0),ux*push); np.add.at(self.pos,(jj,1),uy*push)
            self.pos[:,0]=np.clip(self.pos[:,0],self.r,self.w-self.r)
            self.pos[:,1]=np.clip(self.pos[:,1],self.r,self.h-self.r)
def clusters(pos,link):
    n=len(pos); seen=np.zeros(n,bool); out=[]
    cell={}
    for i,(x,y) in enumerate(pos): cell.setdefault((int(x//link),int(y//link)),[]).append(i)
    for i in range(n):
        if seen[i]: continue
        st=[i]; seen[i]=True; cnt=0
        while st:
            j=st.pop(); cnt+=1
            cx,cy=int(pos[j,0]//link),int(pos[j,1]//link)
            for ox in (-1,0,1):
                for oy in (-1,0,1):
                    for q in cell.get((cx+ox,cy+oy),()):
                        if not seen[q] and np.hypot(*(pos[q]-pos[j]))<link:
                            seen[q]=True; st.append(q)
        out.append(cnt)
    return sorted(out,reverse=True)
def render(w,path,scale=12):
    img=Image.new("RGB",(int(w.w*scale),int(w.h*scale)),(255,255,255)); px=img.load()
    pal=[(220,70,60),(60,130,220),(70,180,90),(240,170,40),(150,80,200),(40,180,180)]
    rr=w.r*scale
    for i in range(w.n):
        cx,cy=w.pos[i,0]*scale,w.pos[i,1]*scale; c=pal[int(w.t[i])%6]
        for a in range(int(cx-rr),int(cx+rr)+1):
            for b in range(int(cy-rr),int(cy+rr)+1):
                if (a-cx)**2+(b-cy)**2<=rr*rr and 0<=a<img.width and 0<=b<img.height: px[a,b]=c
    img.save(path)

