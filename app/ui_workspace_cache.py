"""Display-only compressed browser snapshots; never an operation authority."""
WORKSPACE_CACHE_JS = r'''
    async function readWorkspaceSnapshot(key) {
      try {
        const saved=JSON.parse(sessionStorage.getItem(key)||'null');
        if(saved?.encoding!=='gzip')return saved;
        if(typeof DecompressionStream!=='function')return null;
        const bytes=Uint8Array.from(atob(saved.data),c=>c.charCodeAt(0));
        const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
        return JSON.parse(await new Response(stream).text());
      } catch (_) {return null;}
    }
    async function writeWorkspaceSnapshot(key,value,current=()=>true) {
      try {
        if(!current())return false;
        // Remove the obsolete snapshot BEFORE compression/quota can fail or
        // navigation can interrupt this write. Never leave an older small view.
        sessionStorage.removeItem(key);
        let packed=JSON.stringify(value);
        if(packed.length>=1800000){
          if(typeof CompressionStream!=='function')return false;
          const stream=new Blob([packed]).stream().pipeThrough(new CompressionStream('gzip'));
          const bytes=new Uint8Array(await new Response(stream).arrayBuffer());
          let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
          packed=JSON.stringify({encoding:'gzip',data:btoa(binary)});
        }
        if(!current()||packed.length>=1800000)return false;
        sessionStorage.setItem(key,packed);return true;
      } catch (_) {return false;}
    }
'''
