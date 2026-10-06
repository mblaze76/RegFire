/* Preserve old preview bookmarks without exposing a separate membership page. */
(()=>{
 const id=new URLSearchParams(location.hash.slice(1)).get('event');
 location.replace(/^[a-f0-9-]{36}$/.test(id||'')?'/preview#event='+encodeURIComponent(id)+'&view=registration':'/products');
})();
