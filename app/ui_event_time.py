"""Time defaults used by the workspace and adoption event editors."""

EVENT_TIME_JS = r"""
function nextChildInterval({minDate,maxDate,minTime,maxTime},previous=null){
  if(!minDate || !maxDate)return null;
  let startDate=minDate,startTime=minTime||"00:00";
  if(previous){
    startDate=previous.day;
    const [hours,minutes]=previous.time.split(":").map(Number);
    const next=hours*60+minutes+1;
    if(next<24*60){
      startTime=String(Math.floor(next/60)).padStart(2,"0")+":"+String(next%60).padStart(2,"0");
    }else{
      const date=new Date(startDate+"T00:00:00Z");
      date.setUTCDate(date.getUTCDate()+1);
      startDate=date.toISOString().slice(0,10);
      startTime="00:00";
    }
  }
  if(startDate>maxDate)return {
    error:"Der bisherige Unterereigniszeitraum reicht bereits bis zum Ende des Oberereignisses. Ändere zuerst die letzte Endzeit.",
  };
  const endTime=startDate===maxDate ? (maxTime||"23:59") : "23:59";
  if(startDate===maxDate && startTime>endTime)return {
    error:"Im Oberereignis ist hinter dem letzten Unterereignis kein weiterer Zeitraum frei.",
  };
  return {start_date:startDate,start_time:startTime,end_date:startDate,end_time:endTime};
}
"""
