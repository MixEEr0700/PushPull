// Strict JSON boundary shared by the backup readers. No I/O or normalization.
export function requireThat(condition, message) {
  if (!condition) throw new TypeError(`Backup: ${message}`);
}
export const record = x => x !== null && typeof x === 'object' && !Array.isArray(x);
export const identifier = x => typeof x === 'string' && x.trim().length > 0;
export function freeze(x) {
  if (x && typeof x === 'object') { Object.values(x).forEach(freeze); Object.freeze(x); }
  return x;
}
export function canonical(x) {
  if (Array.isArray(x)) return '['+x.map(canonical).join(',')+']';
  if (record(x)) return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}';
  return JSON.stringify(x);
}
// Compare decimal spellings without rounding them through binary floating point.
function decimal(token) {
  const [,sign,whole,fraction='',exponent='0']=/^(-?)(\d+)(?:\.(\d+))?(?:[Ee]([+-]?\d+))?$/.exec(token);
  let digits=(whole+fraction).replace(/^0+/,'');
  if (!digits) return '0';
  let power=BigInt(exponent)-BigInt(fraction.length);
  while (digits.endsWith('0')) {digits=digits.slice(0,-1);power++;}
  return sign+digits+'e'+power;
}
export function parseJson(text) {
  requireThat(typeof text === 'string', 'expected JSON text');
  const value=JSON.parse(text);
  const stack=[];
  const tokens= /"(?:\\.|[^"\\])*"|[{}\[\]:,]|-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?|true|false|null/g;
  for (const match of text.matchAll(tokens)) {
    const token=match[0];
    if (token==='{') stack.push(new Set());
    else if (token==='[') stack.push(null);
    else if (token==='}' || token===']') stack.pop();
    else if (token.startsWith('"') && /^\s*:/.test(text.slice(match.index+token.length))) {
      const key=JSON.parse(token),keys=stack.at(-1);
      requireThat(!keys.has(key), `duplicate JSON property ${key}`); keys.add(key);
    } else if (/^-?\d/.test(token)) {
      const number=Number(token);
      requireThat(Number.isFinite(number) && !Object.is(number,-0) && decimal(token)===decimal(JSON.stringify(number)), 'number cannot be represented losslessly');
    }
  }
  return value;
}

// Preserve all own JSON keys, including unfamiliar future fields. Reject values
// JSON.stringify would silently change or discard, before cloning or hashing.
export function portable(value, ancestors=new Set()) {
  if (value===null || ['string','boolean'].includes(typeof value)) return;
  if (typeof value==='number') {
    requireThat(Number.isFinite(value) && !Object.is(value,-0), 'non-portable JSON number');return;
  }
  requireThat(typeof value==='object' && !ancestors.has(value), 'non-JSON value or cycle');
  const array=Array.isArray(value);
  requireThat(array || [Object.prototype,null].includes(Object.getPrototypeOf(value)), 'non-plain JSON object');
  requireThat(Object.getOwnPropertySymbols(value).length===0, 'symbol key');
  const keys=Object.getOwnPropertyNames(value).filter(k=>!(array && k==='length'));
  requireThat(!array || keys.length===value.length && keys.every((k,i)=>k===String(i)), 'sparse or decorated array');
  ancestors.add(value);
  for (const key of keys) {
    const descriptor=Object.getOwnPropertyDescriptor(value,key);
    requireThat(descriptor.enumerable && 'value' in descriptor, 'non-JSON property');
    portable(descriptor.value,ancestors);
  }
  ancestors.delete(value);
}
