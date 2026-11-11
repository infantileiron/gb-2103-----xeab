import {useState} from 'react';
import {useDatasets} from '../stores/useDatasets';
import {useStudies} from '../stores/useStudies';
import {createStudy} from '../api/studies';
import {createRun} from '../api/runs';
import {FEATURES} from '../constants/enums';
import {PageTitle} from '../components/common/PageTitle';
import {Feedback} from '../components/common/Feedback';
import {StudyTable} from '../components/StudyTable';
import type {User} from '../types';
export function Studies({user}:{user:User}){
 const ds=useDatasets(),studies=useStudies();
 const [name,setName]=useState(''),[dataset,setDataset]=useState(''),[features,setFeatures]=useState(Object.keys(FEATURES));
 const [maxK,setMaxK]=useState(5),[bootstrap,setBootstrap]=useState(20),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const run=async(id:string)=>{setBusy(true);try{await createRun(id);location.hash='results'}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
 return <><PageTitle eyebrow="03 / STUDY DESIGN" title="先定义问题，再寻找分型。" description="标准化消除量纲差异，候选 k 比较与 Bootstrap 共同约束解释。"/>
 <Feedback error={error||studies.error||ds.error} onRetry={studies.reload}/>
 <div className="split"><section className="section"><div className="section-heading"><h2>研究设计簿</h2><span>固定随机种子 2611</span></div>
 <StudyTable studies={studies.data} datasets={ds.data} onRun={run} disabled={busy||user.role==='viewer'}/>
 <div className="method-note"><span>计算流程</span><p>原始样本 → 标准化 → 多起点 KMeans → 轮廓系数选 k → 重采样重新拟合 → ARI稳定性。</p></div></section>
 <form className="paper-panel" onSubmit={async e=>{e.preventDefault();setBusy(true);try{const s=await createStudy({name,dataset_id:dataset||ds.data[0]?.id,features,min_k:2,max_k:maxK,bootstrap,seed:2611});await studies.reload();setName('');await run(s.id)}catch(err){setError((err as Error).message)}finally{setBusy(false)}}}>
 <span className="eyebrow">新研究 / DESIGN SHEET</span><h2>定义一项分型研究</h2>
 <label>研究名称<input required minLength={2} maxLength={100} value={name} onChange={e=>setName(e.target.value)} placeholder="例如：支汊溶氧分型复核"/></label>
 <label>观测批次<select value={dataset||ds.data[0]?.id||''} onChange={e=>setDataset(e.target.value)}>{ds.data.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
 <fieldset><legend>分析特征（至少2项）</legend>{Object.entries(FEATURES).map(([k,label])=><label className="check" key={k}><input type="checkbox" checked={features.includes(k)} onChange={e=>setFeatures(e.target.checked?[...features,k]:features.filter(f=>f!==k))}/>{label}</label>)}</fieldset>
 <div className="field-pair"><label>最大分组数<input type="number" min="2" max="6" value={maxK} onChange={e=>setMaxK(+e.target.value)}/></label><label>重采样次数<input type="number" min="5" max="60" value={bootstrap} onChange={e=>setBootstrap(+e.target.value)}/></label></div>
 <button className="primary" disabled={busy||user.role==='viewer'||features.length<2}>{busy?'任务处理中…':'保存设计并运行 ↗'}</button><small>任务交由后台计算。可离开当前页，稍后查看分型解释。</small></form></div></>;
}
