import AdminShell from './AdminShell';
export default function AdminEmpty({title,description,detail}:{title:string;description:string;detail:string}){return <AdminShell title={title} description={description}><section className="empty-card"><p className="eyebrow">NO RECORDS YET</p><h2>{detail}</h2><p>Records will appear here as the operational workflow creates them.</p></section></AdminShell>}
