"""Execute the technical presentation and original-log contract in Node."""
import json
from app.ui_i18n import I18N_UI_JS
from tests.backend.test_rc3_mobile import node


def assert_technical_presentation(html, tmp_path):
    start=html.index('    function importUiText(value)')
    end=html.index('    function renderJob(',start)
    escape=html[html.index('    function escapeHtml(value)'):]
    escape=escape[:escape.index('    function formatBytes(')]
    point=html.index('localizedTechnicalJob(job),')
    presentation=html[html.rfind('<pre>',0,point):html.index('</pre>',point)+6]
    point=html.index('<pre data-original-job-log>')
    original=html[point:html.index('</pre>',point)+6]
    sample={'id':'Auftrag-ä<&','name':'Sicherung nicht löschen','path':'/Archiv/Fehler/<img src=x onerror=alert(1)>.JPG',
            'progress_message':'Ordnerimport erfolgreich abgeschlossen. 18 Mediendateien wurden verifiziert.',
            'result':{'note':'Quelle wird vollständig in die temporäre Sicherung kopiert.',
                      'items':[{'warning':'Sicherung abgebrochen','source_label':'Sicherung abgebrochen'}],
                      'sha256':'a'*64,'raw_log':'Sicherung abgebrochen'},
            'html':'<script>alert("raw")</script>'}
    script="""globalThis.localStorage={getItem:()=>null,setItem(){}};
globalThis.document={title:'Import',readyState:'loading',documentElement:{dataset:{bkLocale:'en'}},addEventListener(){},querySelectorAll:()=>[],body:null};
globalThis.window={alert(){throw Error('executed HTML')},confirm(){return false},prompt(){return null},dispatchEvent(){}};
globalThis.CustomEvent=function(){};
"""+I18N_UI_JS+escape+html[start:end]+'\nconst job='+json.dumps(sample,ensure_ascii=False)+""";
const raw=JSON.stringify(job);
function freeze(value){if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value)}}
freeze(job);
const projected=localizedTechnicalJob(job);
if(projected===job||projected.result===job.result)throw Error('presentation must be an independent copy');
if(JSON.stringify(job)!==raw)throw Error('original bytes/values changed');
if(!projected.progress_message.startsWith('Import completed.')||projected.result.note!=='Copying the entire source to a temporary backup.')throw Error('message translation missing');
function protectedValues(a,b){for(const [key,value] of Object.entries(a)){
 if(['progress_message','note','error_message','warning'].includes(key)&&typeof value==='string')continue;
 if(value&&typeof value==='object')protectedValues(value,b[key]);
 else if(JSON.stringify(value)!==JSON.stringify(b[key]))throw Error('opaque value changed: '+key);
}}
protectedValues(job,projected);
"""+'const visible=`'+presentation+'`;\nconst rawMarkup=`'+original+'`;\n'+"""
for(const markup of [visible,rawMarkup]){
 if(/<script|<img|<svg/i.test(markup))throw Error('unescaped data in HTML');
 if(!markup.includes('&lt;img')||!markup.includes('&lt;script'))throw Error('HTML evidence lost');
}
if(!rawMarkup.includes('Ordnerimport erfolgreich abgeschlossen.')||!rawMarkup.includes('Quelle wird vollständig'))throw Error('original messages lost');
window.BibliothekarI18n.setLocale('de');
if(JSON.stringify(localizedTechnicalJob(job))!==raw||JSON.stringify(job)!==raw)throw Error('German/raw values changed');
"""
    node(tmp_path,script)
