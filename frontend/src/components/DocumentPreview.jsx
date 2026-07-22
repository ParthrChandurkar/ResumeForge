import { FaEnvelope, FaGithub, FaGlobe, FaLinkedin, FaPhone } from 'react-icons/fa6'

function Contact({contact={},variant}) {
  const cloud = variant === 'cloud'
  const phoneHref=`tel:${(contact.phone||'').replace(/[^+\d]/g,'')}`, emailHref=`mailto:${contact.email||''}`
  return <div className="doc-contact">{contact.phone&&<a href={phoneHref}><FaPhone/> {contact.phone}</a>}{contact.email&&<a href={emailHref}><FaEnvelope/> {contact.email}</a>}{cloud&&contact.github&&<a href={contact.github} target="_blank" rel="noreferrer"><FaGithub/> {displayUrl(contact.github)}</a>}{contact.linkedin&&<a href={contact.linkedin} target="_blank" rel="noreferrer"><FaLinkedin/> {displayUrl(contact.linkedin)}</a>}{contact.portfolio&&<a href={contact.portfolio} target="_blank" rel="noreferrer"><FaGlobe/> {displayUrl(contact.portfolio)}</a>}</div>
}

function displayUrl(url=''){return url.replace(/^https?:\/\//,'').replace(/\/$/,'')}

export function ResumePreview({ result, printCurrent=false }) {
  const r=result.resume, consulting=result.template_track==='consulting'
  const precision=result.layout_profile==='precision'
  return <article className={`paper resume-paper ${consulting?'consulting-paper':'cloud-paper'} ${precision?'precision-paper':''} ${printCurrent?'print-current':''}`}>
    <header className="resume-header"><h1>{r.contact?.name||'Candidate'}</h1><h2>{r.headline}</h2><Contact contact={r.contact} variant={result.template_track}/></header>
    <DocSection title={r.profile_title}><p>{r.profile}</p></DocSection>
    <DocSection title={r.skills_title} compact>{consulting&&precision&&r.competency_bullets?.length>0&&<div className="competency-grid">{r.competency_bullets.map((item,i)=><span key={i}>{item}</span>)}</div>}{r.skill_groups?.map((group,i)=><p key={i}><strong>{group.label}:</strong> {group.items}</p>)}</DocSection>
    <DocSection title={r.experience_title}>{r.experiences?.map((entry,i)=><DocEntry entry={entry} consulting={consulting&&precision} key={i}/>)}</DocSection>
    {!!r.secondary_entries?.length&&<DocSection title={r.secondary_title}>{r.secondary_entries.map((entry,i)=><DocEntry entry={entry} consulting={consulting&&precision} key={i}/>)}</DocSection>}
    <DocSection title="Education"><div className="entry-head"><strong>{r.education_institution}</strong><strong>{r.education_dates}</strong></div><div className="entry-sub"><em>{r.education_degree}</em><em>{r.education_grade}</em></div>{r.education_coursework&&<p className="dash">Relevant Coursework: {r.education_coursework}</p>}</DocSection>
    <DocSection title={consulting?'Certifications & Professional Development':'Certifications'} compact><ul className="cert-list">{r.certifications?.map((item,i)=><Certification item={item} consulting={consulting} key={i}/>)}</ul></DocSection>
  </article>
}

export function CoverLetterPreview({ result, printCurrent=false }) {
  const l=result.cover_letter
  const today=new Intl.DateTimeFormat('en-US',{month:'long',day:'numeric',year:'numeric'}).format(new Date())
  const contact=l.contact||result.resume?.contact||{}
  return <article className={`paper cover-paper ${printCurrent?'print-current':''}`}><header className="letter-header"><h1><strong>{contact.name||'Candidate'}</strong></h1><Contact contact={contact} variant="cover"/></header><div className="letter-date">{today}</div><div className="recipient"><p>{l.recipient_team}</p><p>{l.company}</p><p>{l.location}</p></div><h2><strong>Re: {l.subject}</strong></h2><p>{l.salutation}</p><p>{l.opening}</p>{l.evidence_sections?.map((section,i)=><section key={i} className="letter-proof"><h3><strong>{section.heading}</strong></h3><p>{section.body}</p></section>)}<p>{l.motivation}</p><p>{l.closing}</p><div className="signature"><p>Yours sincerely,</p><strong>{contact.name||'Candidate'}</strong></div></article>
}

function DocSection({title,children,compact=false}){return <section className={`doc-section ${compact?'compact':''}`}><h3>{title}</h3><div>{children}</div></section>}
function DocEntry({entry,consulting=false}){return <div className="doc-entry"><div className="entry-head"><strong>{entry.title}</strong><strong>{entry.date}</strong></div><div className="entry-sub"><em>{linkEntry(entry.subtitle,entry.url)}</em><em>{entry.location}</em></div>{entry.technologies&&<div className="technologies"><em>{entry.technologies}</em></div>}<ul>{entry.bullets?.map((bullet,i)=><li key={i}>{consulting?<MetricText text={bullet}/>:bullet}</li>)}</ul></div>}

function MetricText({text=''}){const parts=text.split(/(\b\d+(?:\.\d+)?%)/g);return <>{parts.map((part,i)=>/^\d+(?:\.\d+)?%$/.test(part)?<strong key={i}>{part}</strong>:part)}</>}

function linkEntry(text='',url='') { if(!url)return text; const index=text.toLowerCase().indexOf('ieee'); return index<0?<a href={url} target="_blank" rel="noreferrer">{text}</a>:<>{text.slice(0,index)}<a href={url} target="_blank" rel="noreferrer">{text.slice(index)}</a></> }
function Certification({item,consulting}) { const data=typeof item==='string'?{name:item,issuer:'',url:''}:item; const lower=(data.name||'').toLowerCase(); const clean=(data.name||'').replace(/\s*(View Certificate|Verify)\s*$/i,''); return <li><span>{clean}{data.issuer?` – ${data.issuer}`:''}</span>{data.url&&<a href={data.url} target="_blank" rel="noreferrer">{consulting?'Verify':'View Certificate'}</a>}{!data.url&&lower.includes('in progress')&&<em>In Progress</em>}</li> }

export function coverLetterText(result){const l=result.cover_letter,name=l.contact?.name||result.resume?.contact?.name||'Candidate';return [`${l.recipient_team}\n${l.company}\n${l.location}`,`Re: ${l.subject}`,l.salutation,l.opening,...(l.evidence_sections||[]).flatMap(s=>[s.heading,s.body]),l.motivation,l.closing,`Yours sincerely,\n${name}`].join('\n\n')}
