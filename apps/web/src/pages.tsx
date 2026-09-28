import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { displayDate, jsonPost, request, type Claim, type Dataset, type Person, type Preview, type Trait } from './api'
import { useData } from './hooks'

export function DatasetsPage() {
  const datasets = useData<Dataset[]>('/datasets')
  const people = useData<Person[]>('/people')
  const [name, setName] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<{ token: string; preview: Preview } | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  async function create(event: FormEvent) {
    event.preventDefault()
    try {
      const created = await jsonPost<Dataset>('/datasets', { name })
      setDatasetId(created.id); setName(''); datasets.refresh(); setError('')
    } catch (reason) { setError(String(reason)) }
  }
  async function upload(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    const body = new FormData(); body.append('file', file)
    try {
      const value = await request<{ token: string; preview: Preview }>('/import/preview', { method: 'POST', body })
      setPreview(value); setMapping({}); setResult(''); setError('')
    } catch (reason) { setError(String(reason)) }
  }
  async function apply() {
    if (!preview || !datasetId) return
    try {
      const value = await jsonPost<{ imported: number; unmapped_speakers: string[]; already_imported: boolean }>('/import/apply', {
        token: preview.token, dataset_id: datasetId, sha256: preview.preview.sha256, speaker_map: mapping,
      })
      setResult(`${value.imported} imported${value.already_imported ? ' (already imported)' : ''}. Unmapped: ${value.unmapped_speakers.join(', ') || 'none'}`)
      setError('')
    } catch (reason) { setError(String(reason)) }
  }
  const availablePeople = (people.data ?? []).filter(person => person.dataset_id === datasetId)
  return <>
    <header><p className="eyebrow">01 / DATA</p><h1>Datasets</h1><p>Preview a local transcript, confirm speakers, then import it.</p></header>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="panel"><h2>Create dataset</h2><form onSubmit={create} className="row">
      <input aria-label="Dataset name" placeholder="Dataset name" value={name} onChange={event => setName(event.target.value)} required />
      <button>Create</button>
    </form></section>
    <section className="panel"><h2>Import</h2>
      <label>Dataset <select value={datasetId} onChange={event => { setDatasetId(event.target.value); setPreview(null) }}>
        <option value="">Select a dataset</option>{datasets.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <form onSubmit={upload} className="row"><input aria-label="Transcript file" type="file" accept=".json,.jsonl,.csv,.txt,.md,.markdown" onChange={event => setFile(event.target.files?.[0] ?? null)} /><button disabled={!datasetId || !file}>Preview</button></form>
      {preview && <div className="preview"><h3>Preview: {preview.preview.filename}</h3>
        <p>{preview.preview.message_count} messages · {preview.preview.unknown_timestamp} unknown timestamps · {preview.preview.error_count} errors · {preview.preview.warning_count} warnings</p>
        <p>{displayDate(preview.preview.first_timestamp)} → {displayDate(preview.preview.last_timestamp)}</p>
        <h3>Speaker mapping</h3><p className="muted">Unmapped speakers stay unassigned.</p>
        {preview.preview.person_candidates.map(speaker => <label className="mapping" key={speaker}><span>{speaker}</span>
          <select aria-label={`Map ${speaker}`} value={mapping[speaker] ?? ''} onChange={event => setMapping({ ...mapping, [speaker]: event.target.value })}>
            <option value="">Unmapped</option>{availablePeople.map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}
          </select>
        </label>)}
        {[...preview.preview.errors, ...preview.preview.warnings].slice(0, 10).map((issue, index) => <p className="issue" key={index}>{issue.locator}: {issue.message}</p>)}
        <button onClick={apply}>Apply import</button>
      </div>}
      {result && <p role="status" className="success">{result}</p>}
    </section>
    <section className="panel"><h2>Available datasets</h2>{datasets.data?.map(item => <p key={item.id}><strong>{item.name}</strong> <span className="muted">{item.id}</span></p>)}</section>
  </>
}

export function PeoplePage() {
  const people = useData<Person[]>('/people')
  const datasets = useData<Dataset[]>('/datasets')
  const [name, setName] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [error, setError] = useState('')
  async function create(event: FormEvent) {
    event.preventDefault()
    try { await jsonPost('/people', { display_name: name, dataset_id: datasetId }); setName(''); people.refresh(); setError('') }
    catch (reason) { setError(String(reason)) }
  }
  return <><header><p className="eyebrow">02 / ENTITIES</p><h1>People</h1><p>Map imported speaker names to a person before analysis.</p></header>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="panel"><h2>Add person</h2><form onSubmit={create} className="row">
      <select aria-label="Dataset" value={datasetId} onChange={event => setDatasetId(event.target.value)} required><option value="">Dataset</option>{datasets.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <input aria-label="Person name" placeholder="Display name" value={name} onChange={event => setName(event.target.value)} required /><button>Add</button>
    </form></section>
    <section className="cards">{people.data?.map(person => <article className="panel" key={person.id}><h2>{person.display_name}</h2><p className="muted">{datasets.data?.find(item => item.id === person.dataset_id)?.name}</p><Link to={`/people/${person.id}/persona`}>View persona →</Link></article>)}</section>
  </>
}

export function PersonaPage() {
  const { id } = useParams()
  const view = useData<{ person: Person; traits: Trait[]; statistics: { message_count: number; length_mean: number; question_ratio: number } }>(id ? `/people/${id}/persona` : null)
  const claims = useData<Claim[]>(id ? `/people/${id}/claims` : null)
  const [patternStatus, setPatternStatus] = useState('')
  const [distillStatus, setDistillStatus] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [failedJobId, setFailedJobId] = useState<string | null>(null)
  type DistillJob = { id: string; status: string; processed_events: number; total_events: number; result: { claims_created?: number }; error: string | null }
  useEffect(() => {
    if (!jobId) return
    const timer = window.setInterval(async () => {
      try {
        const job = await request<DistillJob>(`/distillation/jobs/${jobId}`)
        setDistillStatus(`${job.status}: ${job.processed_events}/${job.total_events} events`)
        if (job.status === 'completed') {
          setDistillStatus(`Completed: ${job.result.claims_created ?? 0} claims extracted.`)
          setJobId(null); setFailedJobId(null); view.refresh(); claims.refresh()
        } else if (job.status === 'failed') {
          setDistillStatus(`Failed: ${job.error ?? 'unknown error'}`)
          setJobId(null); setFailedJobId(job.id)
        }
      } catch (reason) { setDistillStatus(String(reason)); setJobId(null) }
    }, 1200)
    return () => window.clearInterval(timer)
  }, [jobId, view, claims])
  async function distill() {
    if (!id) return
    try {
      const job = await request<DistillJob>(`/people/${id}/distill`, { method: 'POST' })
      setDistillStatus(`Queued: 0/${job.total_events} events`); setJobId(job.id); setFailedJobId(null)
    } catch (reason) { setDistillStatus(String(reason)) }
  }
  async function retryDistill() {
    if (!failedJobId) return
    try {
      const job = await request<DistillJob>(`/distillation/jobs/${failedJobId}/retry`, { method: 'POST' })
      setJobId(job.id); setFailedJobId(null); setDistillStatus('Retry queued.')
    } catch (reason) { setDistillStatus(String(reason)) }
  }
  async function derivePattern() {
    if (!id) return
    try {
      const result = await jsonPost<{ claim_id: string | null }> (`/people/${id}/meeting-patterns`, {})
      setPatternStatus(result.claim_id ? 'Decision pattern updated.' : 'At least two matching meetings are required.')
      view.refresh(); claims.refresh()
    } catch (reason) { setPatternStatus(String(reason)) }
  }
  return <><header><p className="eyebrow">03 / PERSONA</p><h1>{view.data?.person.display_name ?? 'Persona'}</h1><p>Conclusions are derived from verifiable communication evidence.</p>{id && <Link className="button-link" to={`/simulation/${id}`}>Open AI simulation</Link>}</header>
    {view.error && <p role="alert" className="error">{view.error}</p>}
    <section className="panel"><h2>Observed statistics</h2><p>{view.data?.statistics.message_count ?? 0} messages · average length {view.data?.statistics.length_mean.toFixed(1) ?? '0'} · question ratio {((view.data?.statistics.question_ratio ?? 0) * 100).toFixed(0)}%</p></section>
    <section className="panel"><h2>Evidence distillation</h2><p className="muted">Requires a configured OpenAI-compatible model.</p><button onClick={distill} disabled={Boolean(jobId)}>Distill and rebuild</button>{failedJobId && <button onClick={retryDistill}>Retry failed job</button>}{distillStatus && <p role="status">{distillStatus}</p>}</section>
    <section className="panel"><h2>Traits</h2>{view.data?.traits.length ? view.data.traits.map(trait => <article className="item" key={trait.id}><div className="item-head"><strong>{trait.statement}</strong><span>{Math.round(trait.confidence * 100)}% · {trait.status}</span></div><p className="muted">{trait.dimension} · support {trait.support_count} · counter {trait.counter_count} · first {displayDate(trait.first_seen)} · last {displayDate(trait.last_seen)}</p></article>) : <p className="muted">No distilled traits yet.</p>}</section>
    <section className="panel"><h2>Claims and evidence</h2>{claims.data?.map(claim => <p key={claim.id}><Link to={`/claims/${claim.id}`}>{claim.statement}</Link> <span className="muted">{claim.status} · {Math.round(claim.confidence * 100)}%</span></p>)}</section>
    <section className="panel"><h2>Meeting patterns</h2><p className="muted">Requires matching evidence in at least two meetings.</p><button onClick={derivePattern}>Build decision patterns</button>{patternStatus && <p role="status">{patternStatus}</p>}</section>
  </>
}

export function ClaimPage() {
  const { id } = useParams()
  const view = useData<Claim>(id ? `/claims/${id}` : null)
  const [feedback, setFeedback] = useState('wrong_fact')
  const [note, setNote] = useState('')
  const [correctionStatus, setCorrectionStatus] = useState('')
  async function submitCorrection(event: FormEvent) {
    event.preventDefault()
    if (!view.data) return
    try {
      await jsonPost('/corrections', { person_id: view.data.person_id, target_type: 'claim', target_id: view.data.id, feedback_type: feedback, note })
      setCorrectionStatus('Correction saved.'); view.refresh()
    } catch (reason) { setCorrectionStatus(String(reason)) }
  }
  return <><header><p className="eyebrow">04 / EVIDENCE</p><h1>{view.data?.name ?? 'Claim'}</h1><p>{view.data?.statement}</p></header>
    {view.error && <p role="alert" className="error">{view.error}</p>}
    <section className="panel"><h2>Claim details</h2><p>Status: {view.data?.status} · confidence: {Math.round((view.data?.confidence ?? 0) * 100)}%</p><p>First seen: {displayDate(view.data?.first_seen)} · last seen: {displayDate(view.data?.last_seen)}</p><pre>{JSON.stringify(view.data?.context ?? {}, null, 2)}</pre></section>
    <section className="panel"><h2>Evidence</h2>{view.data?.evidence.map(item => <article className="item" key={item.id}><p><strong>{item.relation}</strong> · “{item.excerpt}”</p><p className="muted">{item.source_file} · {item.source_locator} · {displayDate(item.timestamp)}</p><div className="conversation">{item.context.map(event => <p className={event.is_evidence ? 'focused' : ''} key={event.event_id}><strong>{event.speaker}</strong>: {event.text}</p>)}</div></article>)}</section>
    <section className="panel"><h2>Correct this claim</h2><form onSubmit={submitCorrection}>
      <label>Feedback <select value={feedback} onChange={event => setFeedback(event.target.value)}><option value="wrong_fact">Wrong fact</option><option value="outdated">Outdated</option><option value="wrong_context">Wrong context</option></select></label>
      <label>Correction note<textarea value={note} onChange={event => setNote(event.target.value)} rows={3} /></label><button>Save correction</button>
    </form>{correctionStatus && <p role="status">{correctionStatus}</p>}</section>
  </>
}

export function TimelinePage() {
  const [params, setParams] = useSearchParams()
  const people = useData<Person[]>('/people')
  const personId = params.get('person') ?? ''
  const entries = useData<{ event_id: string; timestamp: string | null; text: string; source_file: string; source_locator: string }[]>(personId ? `/timeline?person_id=${encodeURIComponent(personId)}` : null)
  return <><header><p className="eyebrow">05 / HISTORY</p><h1>Timeline</h1></header><section className="panel"><label>Person <select value={personId} onChange={event => setParams({ person: event.target.value })}><option value="">Select</option>{people.data?.map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}</select></label></section><section className="panel"><h2>Events</h2>{entries.data?.map(item => <article className="item" key={item.event_id}><time>{displayDate(item.timestamp)}</time><p>{item.text}</p><small>{item.source_file} · {item.source_locator}</small></article>)}</section></>
}

type Meeting = {
  id: string; title: string | null; participants: string[]; summary: string;
  speaker_distribution: Record<string, number>;
  decisions: { statement: string; evidence: { event_id: string; source_file: string; source_locator: string; excerpt: string } }[];
  action_items: { owner: string | null; task: string; deadline: string | null; evidence: { event_id: string; source_file: string; source_locator: string } }[];
  utterances: { evidence: { event_id: string; speaker: string; excerpt: string; time_of_day: string | null }; labels: string[] }[];
}

export function MeetingPage() {
  const { id } = useParams()
  const meetings = useData<{ id: string; title: string | null }[]>('/meetings')
  const view = useData<Meeting>(id ? `/meetings/${id}` : null)
  return <><header><p className="eyebrow">08 / MEETINGS</p><h1>{view.data?.title ?? 'Meetings'}</h1><p>Decisions and action items link to explicit utterances.</p></header>
    {!id && <section className="panel"><h2>Conversations</h2>{meetings.data?.map(item => <p key={item.id}><Link to={`/meetings/${item.id}`}>{item.title || item.id}</Link></p>)}</section>}
    {id && <><p><Link to="/meetings">← All meetings</Link></p>{view.error && <p role="alert" className="error">{view.error}</p>}
      <section className="panel"><h2>Overview</h2><p>{view.data?.summary}</p><p>Participants: {view.data?.participants.join(', ')}</p>{Object.entries(view.data?.speaker_distribution ?? {}).map(([speaker, count]) => <p key={speaker}>{speaker}: {count} utterances</p>)}</section>
      <section className="panel"><h2>Decisions</h2>{view.data?.decisions.length ? view.data.decisions.map(item => <article className="item" key={item.evidence.event_id}><p>{item.statement}</p><small>Evidence: {item.evidence.source_file} · {item.evidence.source_locator}</small></article>) : <p className="muted">No explicit decisions found.</p>}</section>
      <section className="panel"><h2>Action items</h2>{view.data?.action_items.map(item => <article className="item" key={item.evidence.event_id}><p>{item.task}</p><p className="muted">Owner: {item.owner || 'Unknown'} · deadline: {item.deadline || 'Unspecified'} · evidence: {item.evidence.source_locator}</p></article>)}</section>
      <section className="panel"><h2>Utterances</h2>{view.data?.utterances.map(item => <article className="item" key={item.evidence.event_id}><p><strong>{item.evidence.speaker}</strong> {item.evidence.time_of_day && <time>{item.evidence.time_of_day}</time>}: {item.evidence.excerpt}</p><small>{item.labels.join(', ') || 'unclassified'}</small></article>)}</section>
    </>}
  </>
}

export function SimulationPage() {
  const { personId } = useParams()
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState('')
  const [turnId, setTurnId] = useState('')
  const [explanation, setExplanation] = useState<{ traits: { statement: string }[]; events: { text: string; source_locator: string }[] } | null>(null)
  const [error, setError] = useState('')
  const [feedbackStatus, setFeedbackStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [topic, setTopic] = useState('')
  const [relationship, setRelationship] = useState('')
  const [scenario, setScenario] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      const result = await jsonPost<{ response: string; turn_id: string }>(`/simulation/${personId}`, { message, context: { channel, topic, relationship, scenario } })
      setResponse(result.response); setTurnId(result.turn_id); setExplanation(null); setError('')
    } catch (reason) { setError(String(reason)) }
  }
  async function explain() {
    try { setExplanation(await request(`/simulation/turns/${turnId}/explain`)) }
    catch (reason) { setError(String(reason)) }
  }
  async function rate(feedback: string) {
    try {
      await jsonPost('/corrections', { person_id: personId, target_type: 'simulation_turn', target_id: turnId, feedback_type: feedback })
      setFeedbackStatus('Feedback saved.')
    } catch (reason) { setFeedbackStatus(String(reason)) }
  }
  return <><div className="disclaimer">AI 模拟，不代表真实人物当前观点。</div><header><p className="eyebrow">06 / SIMULATION</p><h1>Simulation</h1><p>Responses use selected historical evidence and may be uncertain.</p></header>
    {error && <p role="alert" className="error">{error}</p>}
    <section className="panel"><form onSubmit={submit}><label>Your message<textarea value={message} onChange={event => setMessage(event.target.value)} required rows={4} /></label><div className="row"><input aria-label="Channel override" placeholder="Channel (optional)" value={channel} onChange={event => setChannel(event.target.value)} /><input aria-label="Topic override" placeholder="Topic (optional)" value={topic} onChange={event => setTopic(event.target.value)} /><input aria-label="Relationship override" placeholder="Relationship (optional)" value={relationship} onChange={event => setRelationship(event.target.value)} /><input aria-label="Scenario override" placeholder="Scenario (optional)" value={scenario} onChange={event => setScenario(event.target.value)} /></div><button>Generate AI simulation</button></form></section>
    {response && <section className="panel"><h2>AI Simulation</h2><p>{response}</p><div className="row"><button onClick={explain}>Why this response?</button><button onClick={() => rate('like')}>Like</button><button onClick={() => rate('unlike')}>Unlike</button><button onClick={() => rate('wrong_fact')}>Wrong fact</button></div>{feedbackStatus && <p role="status">{feedbackStatus}</p>}{explanation && <div><h3>Selected traits</h3>{explanation.traits.map((item, index) => <p key={index}>{item.statement}</p>)}<h3>Historical examples</h3>{explanation.events.map((item, index) => <p key={index}>{item.text} <small>({item.source_locator})</small></p>)}</div>}</section>}
  </>
}

export function SettingsPage() {
  const settings = useData<{ model_configured: boolean; model_name: string | null; data_location: string }>('/settings')
  return <><header><p className="eyebrow">07 / SETTINGS</p><h1>Settings</h1><p>Local storage and model connection status.</p></header><section className="panel"><p>Model: {settings.data?.model_configured ? settings.data.model_name : 'Not configured'}</p><p>Private data: {settings.data?.data_location ?? 'data/private/'}</p><p className="muted">Set PERSONAFORGE_MODEL_BASE_URL, PERSONAFORGE_MODEL_NAME, and PERSONAFORGE_MODEL_API_KEY in the API environment to enable distillation and simulation.</p></section></>
}
