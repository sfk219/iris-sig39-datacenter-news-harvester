"""IRIS-SIG-39: DataCenter-Insider RSS/Atom to IRIS demo staging."""
from __future__ import annotations
import argparse, hashlib, html, json, logging, os, re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import feedparser, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SOURCE_NAME = "datacenter-insider"
FEED_URL = "https://www.datacenter-insider.de/rss.xml"
TOPICS = {
 "colocation": [r"\bcolo(?:cation)?\b",r"\bco-location\b",r"\brechenzentr\w*\b.{0,90}\b(?:bau|neubau|eröffn\w*|erweiter\w*|invest\w*|standort|campus)\b",r"\b(?:bau|neubau|eröffn\w*|erweiter\w*|invest\w*|standort|campus)\b.{0,90}\brechenzentr\w*\b"],
 "cooling": [r"\bkühl\w*",r"\bcooling\b",r"\bimmersion\b",r"\babwärme\b",r"\bwärmerückgewinn\w*"],
 "energy_compliance": [r"\benergieeffizienzgesetz\b",r"\benergie-effizienzgesetz\b",r"\benefg\b",r"\benergieeffizienz\b",r"\bpue\b",r"\benergy efficiency act\b"]
}
CITIES = {
 "berlin":("DE",13.405,52.52),"frankfurt":("DE",8.6821,50.1109),
 "hamburg":("DE",9.9937,53.5511),"münchen":("DE",11.582,48.1351),
 "stuttgart":("DE",9.1829,48.7758),"köln":("DE",6.9603,50.9375),
 "heilbronn":("DE",9.2183,49.1427),"düsseldorf":("DE",6.7735,51.2277),
 "zürich":("CH",8.5417,47.3769),"genf":("CH",6.1432,46.2044),
 "wien":("AT",16.3738,48.2082),"graz":("AT",15.4395,47.0707)
}
COUNTRIES = {"DE":[r"\bdeutschland\b",r"\bgermany\b"],
 "AT":[r"\bösterreich\b",r"\baustria\b"],
 "CH":[r"\bschweiz\b",r"\bswitzerland\b"]}

@dataclass
class Signal:
 source_name:str
 source_id:str
 signal_type:str
 title:str
 source_url:str
 published_at:str|None
 summary:str
 country_code:str|None
 location_name:str|None
 geo_status:str
 location_note:str
 longitude:float|None
 latitude:float|None
 raw_record:dict

def canonical_url(url):
 p=urlsplit((url or "").strip())
 if p.scheme.lower() not in ("https","http") or not p.hostname: raise ValueError("Invalid article URL")
 query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith(("utm_","fbclid","gclid"))])
 return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or "/",query,""))

def parse_date(raw):
 if not raw:return None
 try:
  try: dt=datetime.fromisoformat(raw.strip().replace("Z","+00:00"))
  except ValueError: dt=parsedate_to_datetime(raw)
  if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(timezone.utc).isoformat()
 except (ValueError,TypeError,OverflowError):return None

def classify(title,summary):
 txt=(title+" "+summary).lower()
 return [label for label,patterns in TOPICS.items() if any(re.search(p,txt,re.I) for p in patterns)]

def location_context(title,summary):
 txt=(title+" "+summary).lower()
 locations=[]
 for name,record in CITIES.items():
  if re.search(r"\b(?:in|bei|nahe|aus|standort(?: in)?|campus(?: in)?)\s+"+re.escape(name)+r"\b",txt,re.I):
   locations.append((name,*record))
 if len(locations)==1:
  name,code,lon,lat=locations[0]
  return code,name,"resolved","Approximate city centroid; not a facility coordinate",lon,lat
 if len(locations)>1:
  codes={v[1] for v in locations}
  return next(iter(codes)) if len(codes)==1 else None,None,"ambiguous","Multiple explicit cities",None,None
 countries=[code for code,pats in COUNTRIES.items() if any(re.search(p,txt,re.I) for p in pats)]
 if not countries and re.search(r"\b(?:enefg|energieeffizienzgesetz)\b",txt):countries=["DE"]
 if len(countries)==1:return countries[0],None,"unresolved","Country only",None,None
 if len(countries)>1:return None,None,"ambiguous","Multiple countries",None,None
 return None,None,"unresolved","No reliable DACH evidence",None,None

def normalize(entry):
 title=re.sub(r"\s+"," ",str(entry.get("title") or "")).strip()
 summary=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(entry.get("summary") or entry.get("description") or "")))).strip()
 if not title:return None,"missing_title"
 try: url=canonical_url(entry.get("link",""))
 except ValueError:return None,"invalid_url"
 if urlsplit(url).hostname not in ("datacenter-insider.de","www.datacenter-insider.de"):return None,"external_url"
 topics=classify(title,summary)
 if not topics:return None,"out_of_domain"
 country,city,status,note,lon,lat=location_context(title,summary)
 if country not in ("DE","AT","CH"):return None,"non_dach_or_unknown"
 if lon is not None and (lat is None or not (-180<=lon<=180 and -90<=lat<=90)):return None,"invalid_coordinates"
 rawdate=entry.get("published") or entry.get("updated") or entry.get("pubDate")
 return Signal(SOURCE_NAME,hashlib.sha256(url.encode()).hexdigest(),",".join(topics),title,url,parse_date(rawdate),summary,country,city,status,note,lon,lat,
               {"guid":entry.get("id") or entry.get("guid"),"date_raw":rawdate,"topics":topics,"feed_source_url":os.getenv("FEED_URL",FEED_URL)}),("invalid_publication_date" if rawdate and not parse_date(rawdate) else None)

def parse_feed(blob):
 parsed=feedparser.parse(blob)
 if parsed.get("bozo"):raise ValueError("Malformed XML feed: "+str(parsed.get("bozo_exception")))
 if not parsed.entries and not parsed.get("version"):raise ValueError("Unrecognized RSS/Atom document")
 return list(parsed.entries)

def fetch_feed(url,timeout=15,retries=3,user_agent="IRIS-SIG-39/1.0"):
 session=requests.Session()
 session.mount("https://",HTTPAdapter(max_retries=Retry(total=retries,backoff_factor=.8,status_forcelist=[429,500,502,503,504],allowed_methods=["GET"])))
 try:
  res=session.get(url,timeout=timeout,headers={"User-Agent":user_agent,"Accept":"application/rss+xml, application/atom+xml, application/xml, text/xml"})
  res.raise_for_status()
  if not res.content:raise ValueError("Empty response")
  if len(res.content)>int(os.getenv("MAX_FEED_BYTES","5242880")):raise ValueError("Response size exceeds safety limit")
  return res.content
 finally:session.close()

UPSERT_SQL="""
INSERT INTO iris_staging.signal_ingest
(source_name,source_id,signal_type,title,source_url,published_at,summary,country_code,location_name,geo_status,location_note,geom,raw_record)
VALUES (%(source_name)s,%(source_id)s,%(signal_type)s,%(title)s,%(source_url)s,%(published_at)s,%(summary)s,%(country_code)s,%(location_name)s,%(geo_status)s,%(location_note)s,
CASE WHEN %(longitude)s IS NULL OR %(latitude)s IS NULL THEN NULL ELSE ST_Transform(ST_SetSRID(ST_MakePoint(%(longitude)s,%(latitude)s),4326),25832) END,%(raw_record)s::jsonb)
ON CONFLICT (source_name,source_id) DO UPDATE SET
signal_type=EXCLUDED.signal_type,title=EXCLUDED.title,source_url=EXCLUDED.source_url,published_at=EXCLUDED.published_at,summary=EXCLUDED.summary,
country_code=EXCLUDED.country_code,location_name=EXCLUDED.location_name,geo_status=EXCLUDED.geo_status,location_note=EXCLUDED.location_note,
geom=EXCLUDED.geom,raw_record=EXCLUDED.raw_record,last_seen_at=now()
RETURNING (xmax=0) AS inserted
"""

def save_signals(signals,dsn):
 import psycopg
 counts={"inserted":0,"updated":0}
 with psycopg.connect(dsn) as conn:
  with conn.cursor() as cur:
   for signal in signals:
    record=asdict(signal)
    record["raw_record"]=json.dumps(record["raw_record"],ensure_ascii=False)
    cur.execute(UPSERT_SQL,record)
    counts["inserted" if cur.fetchone()[0] else "updated"]+=1
 return counts

def process(blob):
 records=parse_feed(blob)
 quality={"fetched":len(records),"accepted":0,"rejected":{},"warnings":{},"geo_status":{}}
 output=[];seen=set()
 for entry in records:
  signal,warning=normalize(entry)
  if signal is None:
   quality["rejected"][warning]=quality["rejected"].get(warning,0)+1
   continue
  if signal.source_id in seen:
   quality["rejected"]["duplicate_in_feed"]=quality["rejected"].get("duplicate_in_feed",0)+1
   continue
  seen.add(signal.source_id)
  if warning:quality["warnings"][warning]=quality["warnings"].get(warning,0)+1
  quality["geo_status"][signal.geo_status]=quality["geo_status"].get(signal.geo_status,0)+1
  output.append(signal)
 quality["accepted"]=len(output)
 return output,quality

def main():
 from dotenv import load_dotenv
 load_dotenv()
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--fixture")
 p.add_argument("--dry-run",action="store_true")
 p.add_argument("--output",default="run/output.jsonl")
 p.add_argument("--report",default="run/quality_report.json")
 args=p.parse_args()
 logging.basicConfig(level=logging.INFO)
 try:
  fixture=args.fixture or os.getenv("FIXTURE_FILE")
  blob=Path(fixture).read_bytes() if fixture else fetch_feed(os.getenv("FEED_URL",FEED_URL),float(os.getenv("HTTP_TIMEOUT",15)),int(os.getenv("HTTP_RETRIES",3)),os.getenv("USER_AGENT","IRIS-SIG-39/1.0"))
  signals,quality=process(blob)
  if args.dry_run:
   path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
   path.write_text("".join(json.dumps(asdict(s),ensure_ascii=False)+"\n" for s in signals),encoding="utf8")
   quality["db"]={"mode":"dry-run","writes":0}
  elif signals:
   dsn=os.getenv("DATABASE_URL")
   if not dsn:raise ValueError("DATABASE_URL required for database writes")
   quality["db"]=save_signals(signals,dsn)
  else:quality["db"]={"writes":0}
  path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(quality,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  print(json.dumps(quality,ensure_ascii=False,indent=2))
  return 0
 except Exception as error:
  logging.exception("Ingestion failed")
  path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps({"status":"failed","error_type":type(error).__name__,"error":str(error)},indent=2)+"\n",encoding="utf8")
  return 1

if __name__=="__main__":raise SystemExit(main())
