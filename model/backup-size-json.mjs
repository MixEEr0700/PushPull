/** Byte counters only. Never returns or builds a serialized document. */
const fail=()=>{throw Object.assign(Error('Measurement unavailable'),{code:'unavailable'})};
const add=(a,b)=>{const n=a+b;if(!Number.isSafeInteger(n))fail();return n};
export function stringProfile(s){
 let bytes=2,quotes=2,slashes=0;
 for(let i=0;i<s.length;i++){
  const c=s.charCodeAt(i);
  if(c===34){bytes+=2;quotes++;slashes++;}
  else if(c===92){bytes+=2;slashes+=2;}
  else if(c<32){bytes+=[8,9,10,12,13].includes(c)?2:6;slashes++;}
  else if(c<128)bytes++;
  else if(c<2048)bytes+=2;
  else if(c>=0xd800&&c<=0xdbff&&s.charCodeAt(i+1)>=0xdc00&&s.charCodeAt(i+1)<=0xdfff){bytes+=4;i++;}
  else if(c>=0xd800&&c<=0xdfff){bytes+=6;slashes++;}
  else bytes+=3;
 }
 return {bytes,quotes,slashes,pretty:bytes,slope:0};
}
export function combineProfiles(items,keys=null){
 const n=items.length;let bytes=2+Math.max(0,n-1),quotes=0,slashes=0,pretty=bytes+(n?n+1+2*n:0),slope=n?2*(n+1):0;
 for(let i=0;i<n;i++){
  const p=items[i],k=keys?stringProfile(keys[i]):null;
  bytes=add(bytes,p.bytes+(k?k.bytes+1:0));pretty=add(pretty,p.pretty+p.slope+(k?k.bytes+2:0));
  quotes+=p.quotes+(k?.quotes??0);slashes+=p.slashes+(k?.slashes??0);slope+=p.slope;
 }
 return {bytes,quotes,slashes,pretty,slope};
}
export function valueProfile(value,depth=0){
 if(depth>96)fail();
 if(typeof value==='string')return stringProfile(value);
 if(value===null||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value)){
  const bytes=String(value).length;return {bytes,quotes:0,slashes:0,pretty:bytes,slope:0};
 }
 if(!value||typeof value!=='object')fail();
 const keys=Object.keys(value);
 if(Array.isArray(value)){if(keys.length!==value.length||keys.some((k,i)=>k!==String(i)))fail();}
 else if(![Object.prototype,null].includes(Object.getPrototypeOf(value)))fail();
 return combineProfiles(keys.map(k=>valueProfile(value[k],depth+1)),Array.isArray(value)?null:keys);
}
/** Stored journalObjects.json is compact JSON written by the protocol. Count
 * its UTF-8 and formatting tokens without parsing large opaque raw strings.
 * This is byte inventory, deliberately NOT the backup integrity validator. */
export function textProfile(text){
 if(typeof text!=='string')fail();
 let bytes=0,quotes=0,slashes=0,extra=0,lines=0,string=false,escape=false;const stack=[];
 for(let i=0;i<text.length;i++){
  const c=text.charCodeAt(i),ch=text[i];
  if(c<128)bytes++;else if(c<2048)bytes+=2;else if(c>=0xd800&&c<=0xdbff&&text.charCodeAt(i+1)>=0xdc00&&text.charCodeAt(i+1)<=0xdfff){bytes+=4;i++;}else if(c>=0xd800&&c<=0xdfff)fail();else bytes+=3;
  if(ch==='"')quotes++;if(ch==='\\')slashes++;
  if(string){if(escape)escape=false;else if(ch==='\\')escape=true;else if(ch==='"')string=false;else if(c<32)fail();continue;}
  if(ch==='"'){string=true;continue;}
  if(ch==='{'||ch==='['){
   const nonempty=text[i+1]!== (ch==='{'?'}':']'),depth=stack.length;
   if(nonempty){extra+=2+2*(2*depth+1);lines+=2;}stack.push(ch);if(stack.length>96)fail();
  }else if(ch==='}'||ch===']'){if(stack.pop()!==(ch==='}'?'{':'['))fail();}
  else if(ch===','){extra+=1+2*stack.length;lines++;}
  else if(ch===':')extra++;
  else if(/\s/.test(ch))fail();
 }
 if(string||escape||stack.length||!bytes)fail();
 return {bytes,quotes,slashes,pretty:bytes+extra,slope:2*lines};
}
export function escapedProfile(p){const bytes=p.bytes+p.quotes+p.slashes+2;return {bytes,quotes:p.quotes+2,slashes:2*p.slashes+p.quotes,pretty:bytes,slope:0};}
