import {flightPlan,flightSample,fleetMapColor} from './fleet-motion.js?v=103';
import {orbitRadii} from './galaxy-map.js?v=20261027-update103';
import {t} from './i18n.js?v=0111';

// Canvas overlay redraws ships only; static map labels and artwork stay cached.
export function mountFleetOverlay(viewport, {systems, positions, now, fleets = [], galaxyId = ''}) {
  const empty={update(){},layout(){},paint(){},destroy(){}};
  const canvas=document.createElement?.('canvas');
  if(!canvas?.getContext)return empty;
  const ctx=canvas.getContext('2d');
  if(!ctx)return empty;
  canvas.className='fleet-map-overlay';
  canvas.setAttribute('aria-hidden','true');viewport.append(canvas);
  const byId=new Map(systems.map(s=>[s.id,s]));
  let width=0,height=0,dpr=1,view={scale:1,x:0,y:0},records=[],frame=0,last=0,dead=false;
  function curve(s) {
    const a=positions().get(s.from_system_id),b=positions().get(s.to_system_id);
    if(!a||!b)return null;
    const from=byId.get(s.from_system_id),to=byId.get(s.to_system_id);
    if(s.kind==='orbit'&&from?.ring_index===to?.ring_index) {
      const radii=orbitRadii(width,height),rx=radii.rx*from.ring_radius,ry=radii.ry*from.ring_radius;
      const angle=Math.atan2((a.y-height/2)/ry,(a.x-width/2)/rx);
      const end=Math.atan2((b.y-height/2)/ry,(b.x-width/2)/rx);
      const delta=Math.atan2(Math.sin(end-angle),Math.cos(end-angle));
      return t=>({x:width/2+Math.cos(angle+delta*t)*rx,y:height/2+Math.sin(angle+delta*t)*ry});
    }
    if(s.kind==='local')return t=>({x:a.x+12*Math.sin(t*Math.PI*2),y:a.y+7*(1-Math.cos(t*Math.PI*2))});
    return t=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});
  }
  function geometry(record) {
    const {plan}=record;
    if(plan.mode!=='normal'&&plan.fromGalaxy!==plan.toGalaxy) {
      const start=plan.segments[0].from_system_id,end=plan.segments[0].to_system_id;
      const departure=galaxyId===plan.fromGalaxy;
      const point=positions().get(departure?start:end);
      if(!point)return [];
      const portal={x:departure?width*.94:width*.06,y:height*.18};
      record.cross=departure?'depart':'arrive';
      return [departure?t=>({x:point.x+(portal.x-point.x)*t,y:point.y+(portal.y-point.y)*t}):
        t=>({x:portal.x+(point.x-portal.x)*t,y:portal.y+(point.y-portal.y)*t})];
    }
    record.cross='';
    return plan.segments.map(segment=>{
      const line=curve(segment),start=Number(segment.from_fraction)||0;
      return line?t=>line(start+(1-start)*t):null;
    });
  }
  function refreshGeometry(){for(const r of records)r.curves=geometry(r);}
  function update(next) {
    records=next.map(f=>({fleet:f,plan:flightPlan(f)})).filter(r=>r.plan.segments.some(s=>byId.has(s.from_system_id)||byId.has(s.to_system_id)));
    refreshGeometry();start();
  }
  function paint() {
    if(!ctx||!width||!height)return;
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
    const visibleNow=now();ctx.save();
    ctx.translate(width/2+view.x,height/2+view.y);ctx.scale(view.scale,view.scale);ctx.translate(-width/2,-height/2);
    for(const r of records) {
      const {fleet,plan}=r,sample=flightSample(fleet,visibleNow,plan);
      const color=fleetMapColor(fleet);
      ctx.strokeStyle=color;ctx.globalAlpha=.4;ctx.lineWidth=1.5/view.scale;
      ctx.setLineDash(plan.mode!=='normal'||plan.segments[0]?.kind==='legacy'?[6/view.scale,5/view.scale]:[]);
      for(const line of r.curves)if(line){ctx.beginPath();for(let i=0;i<=36;i++){const p=line(i/36);i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y);}ctx.stroke();}
      let fraction=sample.fraction,index=sample.index;
      if(r.cross) {
        index=0;
        if((r.cross==='depart'&&sample.progress>.5)||(r.cross==='arrive'&&sample.progress<.5))continue;
        fraction=r.cross==='depart'?sample.progress*2:(sample.progress-.5)*2;
      }
      const line=r.curves[index];if(!line)continue;
      const p=line(fraction),q=line(Math.max(0,fraction-.002)),after=line(Math.min(1,fraction+.002));
      ctx.setLineDash([]);ctx.globalAlpha=1;ctx.save();ctx.translate(p.x,p.y);
      ctx.rotate(Math.atan2(after.y-q.y,after.x-q.x));ctx.scale(1/view.scale,1/view.scale);
      ctx.fillStyle='#03080e';ctx.beginPath();ctx.arc(0,0,12,0,Math.PI*2);ctx.fill();
      const marker=color;
      ctx.strokeStyle=marker;ctx.lineWidth=2;ctx.fillStyle=marker;
      ctx.beginPath();ctx.moveTo(9,0);ctx.lineTo(-6,-5);ctx.lineTo(-3,0);ctx.lineTo(-6,5);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
      if(plan.mode!=='normal') {
        ctx.save();ctx.translate(p.x,p.y);ctx.scale(1/view.scale,1/view.scale);
        ctx.font='12px sans-serif';ctx.fillStyle=color;ctx.fillText(t(plan.mode==='tunnel'?'Tunel':'Lot międzygalaktyczny'),15,-12);ctx.restore();
      }
    }
    ctx.restore();
  }
  function tick(time) {
    if(dead)return;
    if(time-last>=33){last=time;if(!document.hidden&&viewport.isConnected)paint();}
    frame=requestAnimationFrame(tick);
  }
  function start(){if(!frame&&records.length&&!dead)frame=requestAnimationFrame(tick);if(!records.length&&frame){cancelAnimationFrame(frame);frame=0;paint();}}
  update(fleets);
  return {update,
    layout(w,h,nextView){width=w;height=h;view=nextView;dpr=Math.min(2,devicePixelRatio||1);canvas.width=Math.ceil(w*dpr);canvas.height=Math.ceil(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';refreshGeometry();paint();},
    paint(nextView){view=nextView;paint();},
    destroy(){dead=true;cancelAnimationFrame(frame);canvas.remove();}
  };
}


