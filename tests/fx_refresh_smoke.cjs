// Run with: node tests/fx_refresh_smoke.cjs
// Exercise the shipped refresh handler without contacting a bank or Telegram.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/exchange.js'),'utf8');
const handler=source.slice(source.indexOf('async function loadMarketRate('),source.indexOf("$('refreshMarketRate').onclick"));
async function check(reply,expectedRate,expectedSaves,fail=false){
 const elements={}, saved=[];
 const ctx={marketRateBusy:false,lastMarketRateCheckAt:0,fxRate:4090,
  $:id=>elements[id]||(elements[id]={}),t:key=>key,busy:()=>{},
  api:async()=>{if(fail)throw Error('network failure');return reply},
  saveFx:async(silent,rate)=>{saved.push(rate);return true},
  updateRatePreview:()=>{},render:()=>{},renderSummary:()=>{},console};
 vm.createContext(ctx);vm.runInContext(handler,ctx);await ctx.loadMarketRate(true);
 assert.equal(ctx.fxRate,expectedRate);assert.equal(saved.length,expectedSaves);
 assert.equal(ctx.marketRateBusy,false);return elements.marketRateStatus.textContent;
}
(async()=>{
 const quote={rate_khr_per_usd:4075,date:'October 14, 2026 8:10 AM',live:true};
 assert.match(await check(quote,4075,1),/October 14/);
 assert.match(await check({...quote,live:false},4090,0),/marketRateSnapshot/);
 assert.match(await check(null,4090,0,true),/marketRateError/);
 await check({...quote,date:''},4090,0);
 console.log('4 FX refresh cases passed: live saves; stale/error/missing-date keep the saved rate.');
})().catch(e=>{console.error(e);process.exitCode=1;});
