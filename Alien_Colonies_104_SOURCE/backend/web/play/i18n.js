/** Explicit authored-text localization. Dynamic values (player names, chat, IDs)
 * are never translated. HTML tags/attributes are preserved, not string-replaced.
 * Source catalog keys use the same {0} placeholders as the server. */
export const LANGUAGES = {en:'English',pl:'Polski',de:'Deutsch',es:'Español',fr:'Français'};
const browser = typeof document !== 'undefined' && typeof window !== 'undefined';
let language = browser ? 'en' : 'pl';
let catalog = {}, english = {};
if (browser) {
  try { const saved=localStorage.getItem('alien-colonies.language'); if(LANGUAGES[saved]) language=saved; } catch {}
  const explicit=new URLSearchParams(location.search).get('lang'); if(LANGUAGES[explicit]) language=explicit;
}
export const getLanguage = () => language;
export const getLocale = () => ({en:'en-US',pl:'pl-PL',de:'de-DE',es:'es-ES',fr:'fr-FR'}[language]);
export function t(source,...args) {
  const translated = language==='pl' ? source : (catalog[source] ?? english[source] ?? source);
  return String(translated).replace(/\{(\d+)\}/g,(match,index)=>index<args.length ? String(args[index] ?? '') : match);
}
// Create a text key while keeping interpolated values completely opaque.
function translatedPart(part, values) {
  const start=part.match(/^\s*/)[0], end=part.match(/\s*$/)[0];
  let core=part.trim();
  const args=[];
  core=core.replace(/\uE000(\d+)\uE001/g,(_,index)=>{args.push(values[Number(index)]);return `{${args.length-1}}`;});
  if (!/[\p{L}]/u.test(core.replace(/\{\d+\}/g,''))) return part.replace(/\uE000(\d+)\uE001/g,(_,i)=>String(values[Number(i)]??''));
  return start+t(core,...args)+end;
}
function staticTemplate(strings) {return strings.map((part,i)=>part+(i<strings.length-1?`\uE000${i}\uE001`:'')).join('');}
export function text(strings,...values) {return translatedPart(staticTemplate(strings),values);}
export function html(strings,...values) {
  const markup = staticTemplate(strings);
  return markup.replace(/<[^>]*>|[^<]+/g,part=>{
    if(part.startsWith('<')) {
      return part.replace(/\b(title|aria-label|placeholder|alt)=(['"])(.*?)\2/g,(_,attribute,quote,value)=>`${attribute}=${quote}${translatedPart(value,values)}${quote}`)
        .replace(/\uE000(\d+)\uE001/g,(_,i)=>String(values[Number(i)]??''));
    }
    return translatedPart(part,values);
  });
}
export function translateStaticDOM(root=document.body) {
  // Called only once, before any API/player content is mounted.
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes) {
    if(node.parentElement?.closest('script,style,textarea,[data-no-translate]'))continue;
    const source=node.textContent.trim();if(source && /\p{L}/u.test(source))node.textContent=node.textContent.replace(source,t(source));
  }
  for(const el of root.querySelectorAll('[title],[aria-label],[placeholder],[alt]')) {
    for(const attr of ['title','aria-label','placeholder','alt'])if(el.hasAttribute(attr))el.setAttribute(attr,t(el.getAttribute(attr)));
  }
  document.documentElement.lang=language;
  document.title=t(document.title);
}
async function load(code) {
  const response=await fetch(`/play/locales/${code}.json?v=0111`,{cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw new Error('Language files are missing. Please upload the complete web folder.');
  const data=await response.json();if(!data || typeof data!=='object')throw new Error('Invalid language file.');return data;
}
export async function setLanguage(code) {
  if(!LANGUAGES[code])throw new Error('Unsupported language');
  const next=browser?await load(code):{};
  language=code;catalog=next;
  if(browser) {try{localStorage.setItem('alien-colonies.language',code);}catch{} }
}
if(browser) {
  // Imports wait here, so labels stored in other modules are localized on first paint.
  try {
    english=await load('en');catalog=language==='en'?english:language==='pl'?{}:await load(language);
  } catch(error) {
    const box=document.querySelector('#auth-error');
    if(box){box.hidden=false;box.textContent='Unable to load the game language files. Check your connection and reload the page.';}
    throw error;
  }
  translateStaticDOM();
  try {if(localStorage.getItem('alien-colonies.reduce-motion')==='1')document.documentElement.classList.add('reduce-motion');} catch {}
}
