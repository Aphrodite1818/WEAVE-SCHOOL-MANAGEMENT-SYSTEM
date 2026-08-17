import { useEffect, useMemo, useState } from "react";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicLevelService, departmentService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { Input, SelectControl, WorkspaceGrid, WorkspacePanel } from "./AcademicWorkspacePrimitives";

const items = (value) => Array.isArray(value) ? value : value?.items || [];

export default function DepartmentsWorkspace() {
  const { showError, showSuccess } = useToast();
  const [levels,setLevels]=useState([]); const [categories,setCategories]=useState([]); const [levelId,setLevelId]=useState(""); const [departments,setDepartments]=useState([]); const [name,setName]=useState(""); const [saving,setSaving]=useState(false);
  useEffect(()=>{ Promise.all([academicLevelService.getLevels({activeOnly:true}),academicLevelService.getCategories()]).then(([l,c])=>{setLevels(items(l));setCategories(items(c));}).catch(e=>showError(getErrorMessage(e,"Could not load levels."))); },[showError]);
  const eligible=useMemo(()=>{const allowed=new Set(categories.filter(x=>x.supports_departments).map(x=>x.value)); return levels.filter(x=>allowed.has(x.category));},[levels,categories]);
  useEffect(()=>{ if(!eligible.some(x=>x.id===levelId)) setLevelId(eligible[0]?.id||""); },[eligible,levelId]);
  useEffect(()=>{ if(!levelId){setDepartments([]);return;} departmentService.getDepartments(levelId).then(r=>setDepartments(items(r))).catch(e=>showError(getErrorMessage(e,"Could not load departments."))); },[levelId,showError]);
  const create=async(e)=>{e.preventDefault(); if(!name.trim()||!levelId)return; setSaving(true); try{await departmentService.createDepartment(levelId,{name:name.trim()});setName("");setDepartments(items(await departmentService.getDepartments(levelId)));showSuccess("Department created.");}catch(err){showError(getErrorMessage(err,"Could not create department."));}finally{setSaving(false);}};
  return <WorkspaceGrid editor={<WorkspacePanel title="Add department" description="Departments belong to a level. Only categories that support specialization appear here."><form className="space-y-3" onSubmit={create}><SelectControl label="Academic level" value={levelId} onChange={setLevelId} options={eligible.map(x=>({value:x.id,label:x.name}))} required/><Input label="Department name" value={name} onChange={e=>setName(e.target.value)} placeholder="Science" required/><Button type="submit" disabled={saving||!levelId}>{saving?"Saving…":"Add department"}</Button></form></WorkspacePanel>} content={<WorkspacePanel title="Level departments" description="A class is assigned to one of these only for the selected term; the class itself stays unchanged.">{eligible.length===0?<p className="text-sm text-text-muted">No configured level supports departments.</p>:<div className="space-y-2">{departments.map(row=><div key={row.id} className="rounded-xl border border-border/70 px-3 py-3"><p className="font-semibold text-text">{row.name}</p></div>)}{departments.length===0?<p className="text-sm text-text-muted">No departments for this level yet.</p>:null}</div>}</WorkspacePanel>}/>;
}
