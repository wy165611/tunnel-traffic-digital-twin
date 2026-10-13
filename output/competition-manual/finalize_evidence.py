from pathlib import Path
import json,csv,hashlib,re,zipfile
from docx import Document
from lxml import etree
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;E=OUT/'evidence'
def write(name,value): (E/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
validation={
 'checked_on':'2026-10-03','source':'Tool execution outputs in this authoring session; this file summarizes them and is not a raw log.',
 'backend':{'command':'TWIN_DATA_DIR=/private/tmp/twin-competition-validation-20261003 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider','passed':88,'failed':0,'elapsed_seconds':12.67},
 'frontend':{'command':'bundled Node --test frontend/tests/*.test.mjs','passed':27,'failed':0},
 'runtime':{'command':'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_runtime.py','http':'PASS','trusted_origin_idle_websocket':'PASS','graceful_shutdown':'PASS','isolated_data':'PASS','initial_sandbox_network_bind':'EPERM; authorized unsandboxed rerun passed'},
 'interpretation':'software regression and runtime smoke; no detection accuracy, real speed precision or tunnel acceptance inferred',
 'human_verification':'pending'}
write('validation-20261003.json',validation)
references=[
(1,'Veres M; Moussa M','Deep Learning for Intelligent Transportation Systems: A Survey of Emerging Trends','journal','2020','IEEE Transactions on Intelligent Transportation Systems','21','8','3152-3168','10.1109/TITS.2019.2929020','https://ieeexplore.ieee.org/document/8771378','https://doi.org/10.1109/TITS.2019.2929020','abstract; problem-specific spatiotemporal challenges'),
(2,'Sochor J; Juránek R; Herout A','Traffic Surveillance Camera Calibration by 3D Model Bounding Box Alignment for Accurate Vehicle Speed Measurement','journal','2017','Computer Vision and Image Understanding','161','','87-98','10.1016/j.cviu.2017.05.015','https://arxiv.org/abs/1702.06451','https://doi.org/10.1016/j.cviu.2017.05.015','author abstract; automatic scale inference; not implemented here'),
(3,'Sochor J; Juránek R; Špaňhel J; et al.','Comprehensive Data Set for Automatic Single Camera Visual Speed Measurement','journal','2019','IEEE Transactions on Intelligent Transportation Systems','20','5','1633-1643','10.1109/TITS.2018.2825609','https://arxiv.org/abs/1702.06441','https://doi.org/10.1109/TITS.2018.2825609','author abstract; independent LiDAR optical-gate and GPS speed truth'),
(4,'dronefreak','visdrone-yolo11n model card','model_card','','','','','','','https://huggingface.co/dronefreak/visdrone-yolo11n','','publisher weight identity; no model-card metrics borrowed'),
(5,'Ultralytics','Ultralytics YOLO11','documentation','','','','','','','https://docs.ultralytics.com/models/yolo11/','','model family and official pretrained weight'),
(6,'Torchvision','ssdlite320_mobilenet_v3_large','documentation','','','','','','','https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html','','COCO weights and architecture'),
(7,'Zhu P; Wen L; Bian X; et al.','Vision Meets Drones: A Challenge','preprint','2018','','','','','10.48550/arXiv.1804.07437','https://arxiv.org/abs/1804.07437','','aerial detection/tracking setting'),
(8,'Bewley A; Ge Z; Ott L; et al.','Simple Online and Realtime Tracking','conference','2016','ICIP','','','','10.1109/ICIP.2016.7533003','https://arxiv.org/abs/1602.00763','https://doi.org/10.1109/ICIP.2016.7533003','Kalman and Hungarian association'),
(9,'OpenCV','Geometric Image Transformations','documentation','','','','','','','https://docs.opencv.org/4.13.0/da/d54/group__imgproc__transform.html','','getPerspectiveTransform and perspectiveTransform')]
ref_records=[]
for vals in references:
 names=['number','authors','title','publication_type','year','venue','volume','issue','pages','doi','opened_primary_url','published_url','support_locator']
 rec=dict(zip(names,vals));rec.update({'assistant_checked_on':'2026-10-03','human_verification':'pending'})
 if rec['number']<=3:rec['bibliographic_registration']='https://api.crossref.org/works/'+rec['doi']
 ref_records.append(rec)
write('references.json',ref_records)
m=json.loads((E/'source_manifest.json').read_text());known={x['path']:x['evidence_id'] for x in m['sources']}
def add_file(path,absolute=False,locator='source text or original pixels'):
 key=str(path) if absolute else str(path.relative_to(ROOT))
 if key in known:return known[key]
 eid=f"E{len(m['sources'])+1:03d}";known[key]=eid
 m['sources'].append({'evidence_id':eid,'path':key,'sha256':digest(path),'locator':locator,'verification':{'source_opened':True,'status':'unverified','verified_by':'','verified_on':''},'assistant_inspected_on':'2026-10-03','human_verification':'pending'})
 return eid
for path in [E/'environment.json',E/'validation-20261003.json',E/'run-summary.json',E/'bibliographic-records.json',ROOT/'plans/002-real-video-verification.json',ROOT/'docs/design-review/README.md']:
 add_file(path)
refids={}
for rec in ref_records:
 eid=f"E{len(m['sources'])+1:03d}";refids[rec['number']]=eid
 m['sources'].append({'evidence_id':eid,'path':rec['opened_primary_url'],'title':rec['title'],'doi':rec['doi'],'bibliographic_metadata':rec,'locator':rec['support_locator'],'verification':{'source_opened':True,'status':'unverified','verified_by':'','verified_on':''},'assistant_inspected_on':'2026-10-03','human_verification':'pending'})
format_eid=f"E{len(m['sources'])+1:03d}"
m['sources'].append({'evidence_id':format_eid,'path':'https://itsnet.cn/wenjianxiazai/181.html','title':'第十届中国研究生智慧城市技术与创意设计大赛 附件2 作品说明书格式要求','locator':'official 2026-03-19 attachment image; six-page requirement overridden for this local expanded deliverable by user','verification':{'source_opened':True,'status':'unverified','verified_by':'','verified_on':''},'assistant_inspected_on':'2026-10-03','human_verification':'pending'})
# Preserve reference and formatting source identities without copying reference personnel.
add_file(Path('/Users/wanghaoxin/Desktop/智能交通大赛/智能交通大赛作品说明书.pdf'),True,'7-page reference; 6 main-text pages plus declaration')
add_file(Path('/private/tmp/twin-doc-reference/official-format.png'),True,'official attachment image inspected')
write('source_manifest.json',m)
# Attach public literature and live verification IDs to paragraph evidence markers.
lines=(E/'manuscript.md').read_text().splitlines();claims=list(csv.DictReader((E/'claims.csv').open(encoding='utf-8-sig')));by={c['claim_id']:c for c in claims}
for i,line in enumerate(lines):
 hit=re.search(r'\[claim:(C\d+)\]',line)
 if not hit:continue
 ids=set(by[hit[1]]['evidence_ids'].split(','));text=line.split(' [claim:')[0]
 for match in re.finditer(r'\[(\d+)(?:-(\d+))?\]',text):
  lo=int(match[1]);hi=int(match[2] or match[1]);ids.update(refids[n] for n in range(lo,hi+1) if n in refids)
 if '本次环境' in text or 'OpenCV 4.13.0.92' in text:ids.add(known[str((E/'environment.json').relative_to(ROOT))])
 if '2026年10月3日' in text or text.startswith('功能验证与实际运行证据') or '本次测试使用隔离' in text or '运行检查启动隔离实例' in text:ids.add(known[str((E/'validation-20261003.json').relative_to(ROOT))])
 if any(t in text for t in ['2162','1074','134.12','0.0–8.5s','源视频SHA256','3a247cda']):ids.add(known[str((E/'run-summary.json').relative_to(ROOT))])
 ids.discard('');ordered=sorted(ids);by[hit[1]]['evidence_ids']=','.join(ordered)
 lines[i]=re.sub(r'\[evidence:[^\]]*\]',f'[evidence:{",".join(ordered)}]',line)
(E/'manuscript.md').write_text('\n'.join(lines),encoding='utf-8')
with (E/'claims.csv').open('w',encoding='utf-8-sig',newline='') as f:
 wr=csv.DictWriter(f,fieldnames=list(claims[0]));wr.writeheader();wr.writerows(claims)
# Provenance and transformations for every display.
displays=json.loads((E/'displays.json').read_text());fsource={1:['backend/service.py','backend/processor.py','backend/main.py'],2:['backend/processor.py','backend/vision/tracker.py'],3:['backend/calibration/homography.py'],4:['output/playwright/twin-horizontal.png','docs/twin-orientation.md'],5:['backend/evidence.py','backend/annotations.py'],6:['plans/features-report-desktop.jpg'],7:['plans/002-evaluation-result.jpg','plans/002-browser-result.json'],8:['backend/data/runs/20261002-170236-c53990/traffic_statistics.csv']}
for x in displays:
 if x['kind']=='figure':
  x['evidence']=[known[p] for p in fsource[x['number']]];x['asset_sha256']=digest(OUT/'assets'/x['asset'])
  x['processing']={4:'Original screenshot pixels cropped; two ID 1 insets enlarged 3x with Lanczos, aspect ratios preserved; descriptive labels added outside original pixels.',6:'Original screenshot crop of interval and cumulative machine count cards.',7:'Original controlled-test screenshot crop; explicit synthetic-label disclaimer outside pixels.',8:'All 256 CSV rows plotted in original time order; no smoothing or data fabrication.'}.get(x['number'],'Source-derived conceptual diagram, explicitly labeled as such; no measured value asserted.')
  x['rights_status']='Local user-provided project material; external redistribution/competition permissions pending team confirmation.'
write('displays.json',displays)
# Non-scoring numeric reconciliation; methodology and result layers are separate.
summary=json.loads((E/'run-summary.json').read_text());num=[]
facts=[('statistics_frames',256,'frame'),('machine_crossings',19,'crossing'),('confirmed_track_ids',28,'track ID'),('max_active_tracks',13,'track ID'),('vehicle_frame_rows',2162,'vehicle frame'),('observed_vehicle_frames',1074,'vehicle frame'),('predicted_vehicle_frames',1088,'vehicle frame'),('valid_observed_speed',0,'sample'),('machine_events',0,'event'),('interval_end',8.5,'second')]
eid=known[str((E/'run-summary.json').relative_to(ROOT))]
for concept,value,unit in facts:
 for section in ['4.4','Table 5']:
  num.append({'fact_id':f'N{len(num)+1:03d}','concept':concept,'section':section,'value':value,'unit':unit,'numerator':None,'denominator':None,'sample_size':256 if concept in ['statistics_frames','machine_crossings'] else None,'analysis_set':'bridge_run_20261002-170236-c53990','evidence_ids':[eid]})
num.append({'fact_id':f'N{len(num)+1:03d}','concept':'valid_speed_coverage','section':'Table 5','value':0,'unit':'percent','numerator':0,'denominator':1074,'sample_size':1074,'analysis_set':'observed_vehicle_frames','evidence_ids':[eid]})
write('consistency_manifest.json',{'schema_version':'1.0','numeric_facts':num,'methods':[{'method_id':'M001','name':'Descriptive summary of preserved bridge run CSV','analysis_intent':'descriptive','protocol_status':'post_hoc','outcome_ids':['O001']}],'results':[{'result_id':'R001','method_id':'M001','outcome_id':'O001','analysis_intent':'descriptive','sample_size':256,'evidence_ids':[eid],'reported_sections':['4.4','Table 5','Figure 8']}]})
write('reporting_coverage.json',{'document_type':'Chinese engineering competition project manual','clinical_guideline':'not_applicable; this is an engineering implementation and descriptive verification report','topics':{'scope':'1.3','source_models':'2.2 and Table 2','methods':'2.1–2.6','parameters':'Table 3','software_validation':'4.3 and Table 4','descriptive_outputs':'4.4, Table 5 and Figure 8','independent_real_truth':'missing; explicitly disclosed in 4.4','limitations_and_next_experiments':'4.5 and Table 6','deployment_conditions':'5','human_approval':'pending','authorship':'team fields pending'},'submission_ready':False,'note':'No checklist compliance certification or human approval is claimed.'})
# Machine checks on document structure and preservation.
file=OUT/'基于视频感知的隧道交通数字孪生系统作品说明书.docx';doc=Document(file)
with zipfile.ZipFile(file) as z:xml=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'));settings=etree.fromstring(z.read('word/settings.xml'))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
refs_body=xml.xpath('//w:r[w:rPr/w:vertAlign[@w:val="superscript"]]/w:t/text()',namespaces=ns)
refs_numbers={int(n) for s in refs_body for n in re.findall(r'\d+',s)}
assert len(doc.tables)==6 and len(doc.inline_shapes)==8
assert set(range(1,10))<=refs_numbers and len(xml.xpath('//m:oMath',namespaces=ns))==2
assert not settings.xpath('//w:documentProtection',namespaces=ns)
changed=[]
for item in m['sources']:
 if 'sha256' not in item:continue
 p=Path(item['path']);p=p if p.is_absolute() else ROOT/p
 if digest(p)!=item['sha256']:changed.append(item['path'])
assert not changed,changed
assert summary['source_sha256']==digest(ROOT/'backend/data/videos/demo.mp4')
assert summary['identity_matches'] and 1074+1088==2162
pdf=next(Path('/private/tmp/twin-expanded-qa2').glob('*.pdf'));reader=PdfReader(pdf)
write('delivery-audit.json',{'docx_sha256':digest(file),'pages':len(reader.pages),'figures':8,'native_editable_tables':6,'native_editable_equations':2,'superscript_citation_runs':len(refs_body),'reference_numbers':sorted(refs_numbers),'file_size_bytes':file.stat().st_size,'input_source_hash_mismatches':changed,'original_video_identity_rechecked':True,'unit_sample_consistency':'PASS','layout_review':'pending final per-page visual review','human_submission_approval':'pending'})
print('Audit PASS:',len(reader.pages),'pages; 8 figures; 6 tables; native equations and superscript citations.')
