"""Deterministic standardized KMeans selection and bootstrap partition stability."""
import hashlib,json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score,adjusted_rand_score
from sklearn.preprocessing import StandardScaler
from src.constants.enums import FEATURES

def validate_rows(rows,features=FEATURES):
    if len(rows)<10 or len(rows)>5000: raise ValueError("样方数须为10–5000")
    try: x=np.array([[float(row[key]) for key in features] for row in rows],dtype=float)
    except (KeyError,ValueError,TypeError): raise ValueError("存在缺失或非数值特征，请修正后重试")
    if not np.isfinite(x).all(): raise ValueError("特征不允许为空或无限值")
    if (np.std(x,axis=0)<1e-10).any(): raise ValueError("常量特征无法参与标准化分型")
    return x

def analyze(rows,features,min_k=2,max_k=5,bootstrap=20,seed=2611):
    x=validate_rows(rows,features)
    if min_k<2 or max_k<min_k or max_k>6 or max_k>=len(x): raise ValueError("分组数须2–6且小于样本数")
    if not 5<=bootstrap<=60: raise ValueError("稳定性重采样次数须5–60")
    if len(np.unique(x,axis=0))<max_k: raise ValueError("不同样方数不足最大分组数")
    scaler=StandardScaler().fit(x)
    z=scaler.transform(x)
    models=[]
    for k in range(min_k,max_k+1):
        model=KMeans(n_clusters=k,n_init=12,random_state=seed).fit(z)
        score=float(silhouette_score(z,model.labels_,sample_size=min(len(z),1500),random_state=seed))
        models.append((score,k,model))
    score,k,best=max(models,key=lambda row: (row[0],-row[1]))
    labels=best.labels_
    centers=scaler.inverse_transform(best.cluster_centers_)
    # Cluster identities are sorted by the first selected feature for stable reporting.
    order=np.argsort(centers[:,0]); remap={int(old):int(new) for new,old in enumerate(order)}
    labels=np.array([remap[int(i)] for i in labels])
    rng=np.random.default_rng(seed)
    stability=[]
    for i in range(bootstrap):
        indices=rng.integers(0,len(x),len(x)); sample=x[indices]
        s=StandardScaler().fit(sample)
        m=KMeans(n_clusters=k,n_init=8,random_state=seed+i+1).fit(s.transform(sample))
        stability.append(float(adjusted_rand_score(labels,m.predict(s.transform(x)))))
    profiles=[]
    for cluster_id,old in enumerate(order):
        subset=x[labels==cluster_id]
        profiles.append({"cluster_id":cluster_id,"name":f"生态类型 {cluster_id+1}","size":len(subset),"centroid":{f:round(float(subset[:,j].mean()),4) for j,f in enumerate(features)}})
    correlation=np.corrcoef(x,rowvar=False).tolist()
    points=[{"sample_id":row.get("sample_id",str(i+1)),"section":row.get("section","未标注"),"x":float(z[i,0]),"y":float(z[i,1]),"cluster":int(labels[i]),"values":{f:float(row[f]) for f in features}} for i,row in enumerate(rows)]
    return {"selected_k":k,"silhouette":round(score,6),"candidates":[{"k":n,"silhouette":round(s,6)} for s,n,_ in models],"stability":{"mean_ari":round(float(np.mean(stability)),6),"p05":round(float(np.quantile(stability,.05)),6),"p95":round(float(np.quantile(stability,.95)),6),"replicates":bootstrap,"values":stability},"profiles":profiles,"points":points,"features":list(features),"correlation":correlation,"row_count":len(rows),"seed":seed,"checksum":hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),"method":"StandardScaler + KMeans; bootstrap refits scaler and predicts the original sample; ARI is partition stability, not biological truth."}
