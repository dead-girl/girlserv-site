(function(){
  const BASE_STAT_URLS = [
    "base_user_stats.json",
    "./base_user_stats.json",
    "channel-stats/base_user_stats.json"
  ];
  const LIVE_STAT_URLS = [
    "live_truth_seekers_user_stats.json",
    "./live_truth_seekers_user_stats.json",
    "channel-stats/live_truth_seekers_user_stats.json"
  ];

  async function fetchFirstJson(urls){
    for(const url of urls){
      try{
        const res = await fetch(url + "?v=" + Date.now(), { cache: "no-store" });
        if(res.ok) return await res.json();
      }catch(e){}
    }
    return {};
  }

  function addStats(target, nick, stats){
    if(!nick || !stats || typeof stats !== "object") return;
    const key = String(nick);
    if(!target[key]) target[key] = { words:0, joins:0, lol:0, degeneracy:0, links:0 };
    target[key].words += Number(stats.words || 0);
    target[key].joins += Number(stats.joins || 0);
    target[key].lol += Number(stats.lol || stats.lols || 0);
    target[key].degeneracy += Number(stats.degeneracy || stats.bad_words || 0);
    target[key].links += Number(stats.links || 0);
  }

  function mergeStats(base, live){
    const merged = {};
    Object.entries(base || {}).forEach(([nick, stats]) => addStats(merged, nick, stats));
    Object.entries(live || {}).forEach(([nick, stats]) => addStats(merged, nick, stats));
    return merged;
  }

  window.loadMergedGirlServStats = async function(){
    const base = await fetchFirstJson(BASE_STAT_URLS);
    const live = await fetchFirstJson(LIVE_STAT_URLS);
    return mergeStats(base, live);
  };
})();
