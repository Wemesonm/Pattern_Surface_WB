"""PAT-REQ-060: Diamond overlay of the public logical/physical map carrier.

No CAD, GUI, or Blender dependency. Coordinates remain in millimeters.
"""
import math
from collections import Counter


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def clip(poly, triangle):
    sign=1 if cross(*triangle)>0 else -1
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        if not poly:break
        result=[]
        for p,q in zip(poly,poly[1:]+poly[:1]):
            dp,dq=sign*cross(a,b,p),sign*cross(a,b,q)
            if dp>=-1e-9:result.append(p)
            if (dp>=-1e-9)!=(dq>=-1e-9):
                t=dp/(dp-dq)
                result.append(tuple(p[k]+t*(q[k]-p[k]) for k in range(3)))
        poly=result
    return poly


def lattice_cell(row,col,side,height,origin):
    def p(r,c):return (origin[0]+(c+.5*(r%2))*side,origin[1]+r*height,0.)
    a,b,c,d=p(row,col),p(row,col+1),p(row+1,col),p(row+1,col+1)
    return [(a,b,d),(a,d,c)] if row%2 else [(a,b,c),(b,d,c)]


def dimensions(payload, params):
    h=float(params['diamond_height']);r=float(params['pyramid_height'])
    if not all(math.isfinite(v) and v>0 for v in (h,r)):
        raise ValueError('As alturas devem ser positivas e finitas.')
    side=2*h/math.sqrt(3);modules=0;period=None
    adjustments=payload.get('periodic_adjustments',[])
    if adjustments:
        if len(adjustments)!=1 or int(adjustments[0].get('axis',-1))!=0:
            raise ValueError('Este mapa possui fechamento em mais de um eixo; ainda não suportado pelo Blender.')
        period=float(adjustments[0]['period']);modules=max(1,round(period/side))
        error=abs(period-modules*side)
        if error>float(params.get('closure_fit_tolerance',.2))+1e-8:
            raise ValueError('Fechamento requer ajuste de %.3f mm; aumente a tolerância ou ajuste a altura.'%error)
        side=period/modules
    return dict(height=h,relief=r,side=side,modules=modules,period=period)


def build(payload,params,axis=None):
    dim=dimensions(payload,params);S,H=dim['side'],dim['height']
    carrier=payload.get('carrier_triangles',payload.get('triangles',[]))
    if not carrier:raise ValueError('O mapa não contém superfície física.')
    origin=list(payload.get('grid',{}).get('origin',[0,0]))[:2]
    if dim['period']:
        origin[0]=payload['periodic_adjustments'][0]['lower']
    offset=float(params.get('finish_offset',.045));contact=float(params.get('contact',.25))
    step=float(params.get('resolution',.8))
    vertices=[];normals=[];faces=[];facet_ids=[];cache={};facets={}
    def add(p,n,relief):
        # Project relief off the inferred longitudinal axis to preserve rounded-end heights.
        direction=list(n)
        if axis is not None:
            d=sum(n[k]*axis[k] for k in range(3));direction=[n[k]-d*axis[k] for k in range(3)]
        out=tuple(p[k]+direction[k]*(relief+offset) for k in range(3))
        key=tuple(round(v,5) for v in out)
        if key not in cache:
            cache[key]=len(vertices);vertices.append(out);normals.append(tuple(p[k]-n[k]*contact for k in range(3)))
        return cache[key]
    processed=0
    for carrier_tri in carrier:
        vs=carrier_tri['v'];qs=[v['q'] for v in vs];den=cross(*qs)
        if abs(den)<1e-12:continue
        row0=math.floor((min(q[1] for q in qs)-origin[1])/H)
        row1=math.floor((max(q[1] for q in qs)-origin[1])/H)
        col0=math.floor((min(q[0] for q in qs)-origin[0])/S)-1
        col1=math.floor((max(q[0] for q in qs)-origin[0])/S)+1
        for row in range(row0,row1+1):
            for col in range(col0,col1+1):
                for orientation,tri in enumerate(lattice_cell(row,col,S,H,origin)):
                    apex=(sum(p[0] for p in tri)/3,sum(p[1] for p in tri)/3,dim['relief'])
                    for k in range(3):
                        polygon=clip([tri[k],tri[(k+1)%3],apex],qs)
                        if len(polygon)<3:continue
                        key=(row,col%dim['modules'] if dim['modules'] else col,orientation,k)
                        fid=facets.setdefault(key,len(facets)+1)
                        for j in range(1,len(polygon)-1):
                            points=[polygon[0],polygon[j],polygon[j+1]]
                            if abs(cross(*points))<1e-10:continue
                            # Carrier is already fine on curves. Planar faces need no extra tessellation.
                            ids=[]
                            for q in points:
                                weights=(cross(qs[1],qs[2],q)/den,cross(qs[2],qs[0],q)/den,cross(qs[0],qs[1],q)/den)
                                p=[sum(v['p'][a]*w for v,w in zip(vs,weights)) for a in range(3)]
                                n=[sum(v['n'][a]*w for v,w in zip(vs,weights)) for a in range(3)]
                                length=math.sqrt(sum(x*x for x in n))
                                if length<1e-9:raise ValueError('Normal inválida no mapa.')
                                n=[x/length for x in n];ids.append(add(p,n,q[2]))
                            if len(set(ids))==3:faces.append(tuple(ids));facet_ids.append(fid)
                        processed+=1
                        if len(faces)>1500000:raise ValueError('Padrão muito denso; aumente o tamanho dos triângulos.')
    if not faces:raise ValueError('Nenhuma célula intersecta a superfície.')
    return vertices,faces,facet_ids,normals,dim
