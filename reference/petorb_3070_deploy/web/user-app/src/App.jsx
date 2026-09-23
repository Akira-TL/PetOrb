import { useEffect, useMemo, useState } from 'react'
import PetsRounded from '@mui/icons-material/PetsRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import HealthAndSafetyOutlined from '@mui/icons-material/HealthAndSafetyOutlined'
import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded'
import PlayCircleOutlineRounded from '@mui/icons-material/PlayCircleOutlineRounded'
import NotificationsNoneRounded from '@mui/icons-material/NotificationsNoneRounded'
import ArticleOutlined from '@mui/icons-material/ArticleOutlined'
import CalendarMonthOutlined from '@mui/icons-material/CalendarMonthOutlined'
import HomeRounded from '@mui/icons-material/HomeRounded'
import PersonOutlineRounded from '@mui/icons-material/PersonOutlineRounded'
import EcoRounded from '@mui/icons-material/SpaRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import WifiOffRounded from '@mui/icons-material/WifiOffRounded'
import VideocamRounded from '@mui/icons-material/VideocamRounded'
import petIllustration from './assets/pet-illustration.png'
import { keepPeakScores, restoredPeakUser } from './scoreHistory.js'

const previewMode = new URLSearchParams(window.location.search).get('preview') === '1'
const previewData = {
  banner: { level: 'low', text: '未发现明显异常，但建议定期观察。' },
  scores: {
    ulcer: { conf: 0.87, found: true },
    tartar: { conf: 0.64, found: true },
  },
  risk: '低',
  risk_level: 'low',
  updated_ms: new Date('2024-04-26T10:24:00').getTime(),
  frames: 1,
}

const navItems = [
  { id: 'home', label: '首页', Icon: HomeRounded },
  { id: 'replay', label: '回放', Icon: PlayCircleOutlineRounded },
  { id: 'remind', label: '提醒', Icon: NotificationsNoneRounded },
  { id: 'mine', label: '我的', Icon: PersonOutlineRounded },
]

function formatTime(ms) {
  if (!ms) return '等待本次检查'
  const d = new Date(ms)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function displayBanner(text) {
  return (text || '').replaceAll('口腔溃疡', '牙龈相关区域')
}

function useCheckData() {
  const [user, setUser] = useState(() => previewMode ? previewData : restoredPeakUser())
  const [replays, setReplays] = useState([])
  const [error, setError] = useState(false)

  useEffect(() => {
    if (previewMode) return undefined
    let active = true
    async function refresh() {
      try {
        const [u, r] = await Promise.all([
          fetch('/api/user', { cache: 'no-store' }),
          fetch('/api/replay', { cache: 'no-store' }),
        ])
        if (!u.ok || !r.ok) throw new Error('API unavailable')
        const [nextUser, nextReplay] = await Promise.all([u.json(), r.json()])
        if (active) {
          setUser(keepPeakScores(nextUser, nextReplay.items || []))
          setReplays(nextReplay.items || [])
          setError(false)
        }
      } catch {
        if (active) setError(true)
      }
    }
    refresh()
    const timer = window.setInterval(refresh, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  return { user, replays, error }
}

function ScoreCard({ Icon, title, score, note, hasResult }) {
  const value = score?.found ? Math.round(score.conf * 100) : null
  return (
    <article className="score-card">
      <div className="flex items-center gap-2.5">
        <div className="score-icon"><Icon sx={{ fontSize: 29 }} /></div>
        <div className="min-w-0">
          <h3>{title}</h3>
          <p>最高检测置信度</p>
        </div>
      </div>
      <div className="score-number">{value === null ? (hasResult ? <span className="not-found">未检出</span> : '--') : <>{value}<span>%</span></>}</div>
      <div className="score-track" role="meter" aria-label={`${title}最高检测置信度`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? 0}>
        <div style={{ width: `${value ?? 0}%` }} />
      </div>
      <p className="score-note">{score?.found ? note : !hasResult ? '连接设备后显示观察结果。' : '未见明显相关区域，建议持续观察。'}</p>
    </article>
  )
}

function QuickLink({ Icon, title, description, onClick, disabled = false }) {
  return (
    <button className="quick-link" type="button" onClick={onClick} disabled={disabled}>
      <span className="quick-icon"><Icon sx={{ fontSize: 27 }} /></span>
      <span className="quick-copy"><strong>{title}</strong><small>{description}</small></span>
      {disabled ? <span className="soon">敬请期待</span> : <ChevronRightRounded className="quick-arrow" />}
    </button>
  )
}

function Home({ user, hasResult, stale, onNavigate, onOpenLive }) {
  const riskLevel = user?.risk_level || 'idle'
  const hasData = hasResult && !stale
  const isHigh = riskLevel === 'high'
  const isMedium = riskLevel === 'medium'
  const riskTitle = !hasResult ? '等待观察结果' : isHigh ? '较高风险提示' : isMedium ? '中度风险提示' : '轻度风险提示'
  const riskCopy = !hasResult ? '结果会在完成观察后更新。' : displayBanner(user?.banner?.text) || '建议定期观察。'

  return (
    <div className="home-page">
      <section className="hero-card">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2>本次检查</h2>
            <p className="check-time">{formatTime(user?.updated_ms)}</p>
          </div>
          <span className={`completed-pill ${!hasData ? 'pending' : ''}`}>{hasData ? <CheckRounded sx={{ fontSize: 20 }} /> : <span className="pending-dot" />}{hasData ? '已完成观察' : stale ? '上次观察' : '等待画面'}</span>
        </div>
        <div className="hero-body">
          <div className="illustration-slot"><img src={petIllustration} alt="开心的宠物犬插画" /></div>
          <div className="hero-message">
            <button className="summary-box" type="button" onClick={onOpenLive} aria-label="打开实时画面">
              <span className="summary-heading"><VideocamRounded sx={{ fontSize: 20 }} /><strong>实时画面</strong><ChevronRightRounded sx={{ fontSize: 20 }} /></span>
              <span className="summary-detail">点击查看手机传来的实时画面</span>
            </button>
            <button className={`risk-box ${isHigh ? 'risk-high' : ''}`} type="button" onClick={() => onNavigate('remind')}>
              <span className="risk-heading"><WarningAmberRounded sx={{ fontSize: 22 }} /><b>{riskTitle}</b></span>
              <span className="risk-detail">{riskCopy}</span>
              <ChevronRightRounded className="risk-arrow" sx={{ fontSize: 22 }} />
            </button>
          </div>
        </div>
      </section>

      <div className="score-grid">
        <ScoreCard Icon={HealthAndSafetyOutlined} title="牙龈相关区域" score={user?.scores?.ulcer} note="曾识别到牙龈相关区域，保留最高值。" hasResult={hasResult} />
        <ScoreCard Icon={AutoAwesomeRounded} title="牙结石" score={user?.scores?.tartar} note="曾识别到牙结石相关区域，保留最高值。" hasResult={hasResult} />
      </div>

      <div className="shortcut-heading flex items-end justify-between">
        <h2>快捷入口</h2>
        <span>让爱宠的健康管理更简单 <ChevronRightRounded sx={{ fontSize: 17 }} /></span>
      </div>
      <div className="shortcut-grid">
        <QuickLink Icon={PlayCircleOutlineRounded} title="检查回放" description="查看历史检查记录" onClick={() => onNavigate('replay')} />
        <QuickLink Icon={NotificationsNoneRounded} title="AI 提醒" description="定期关注口腔健康" onClick={() => onNavigate('remind')} />
        <QuickLink Icon={ArticleOutlined} title="演示档案" description="体验检测功能" onClick={() => onNavigate('mine')} />
        <QuickLink Icon={CalendarMonthOutlined} title="预约医生" description="专业兽医在线咨询" disabled />
      </div>
      <div className="disclaimer"><EcoRounded sx={{ fontSize: 18 }} />PetOrb 提供辅助风险观察，不构成医疗诊断。</div>
    </div>
  )
}

function LiveWindow({ onClose }) {
  const [frame, setFrame] = useState(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let active = true
    let timer
    async function refresh() {
      let isLive = false
      try {
        const response = await fetch('/api/live-status', { cache: 'no-store' })
        if (!response.ok) throw new Error('Live status unavailable')
        const status = await response.json()
        isLive = Boolean(status.connected)
        if (isLive) {
          const url = `/live.jpg?t=${Date.now()}`
          await new Promise((resolve) => {
            const image = new Image()
            image.onload = () => { if (active) setFrame(url); resolve() }
            image.onerror = resolve
            image.src = url
          })
        }
      } catch {
        isLive = false
      }
      if (!active) return
      setConnected(isLive)
      if (!isLive) setFrame(null)
      timer = window.setTimeout(refresh, isLive ? 150 : 500)
    }
    refresh()
    return () => { active = false; window.clearTimeout(timer) }
  }, [])

  return <div className="modal-backdrop live-backdrop" role="presentation" onClick={onClose}>
    <section className="live-modal" role="dialog" aria-modal="true" aria-label="实时画面" onClick={e => e.stopPropagation()}>
      <header className="live-header"><div><h2>实时画面</h2><span className={`live-status ${connected ? 'connected' : ''}`}><i />{connected ? '直播中' : '等待画面'}</span></div><button className="live-close" type="button" onClick={onClose} aria-label="关闭实时画面"><CloseRounded /></button></header>
      <div className="live-stage">{connected && frame ? <img src={frame} alt="手机传来的实时画面" /> : <div className="live-empty"><VideocamRounded sx={{ fontSize: 46 }} /><strong>正在等待手机画面</strong><p>请在手机预览中开启“传到电脑检测”</p></div>}</div>
      <p className="live-hint">画面来自当前连接的手机，连接中断后会自动等待新画面。</p>
    </section>
  </div>
}

function Replay({ replays, onNavigate }) {
  const [selected, setSelected] = useState(null)
  const current = replays.find(item => item.id === selected) || replays[0]
  return (
    <section className="sub-page">
      <h2>检查回放</h2><p className="sub-lead">检测到可疑区域时，会在本次服务中保存带框画面。</p>
      {current ? <>
        <div className="replay-view"><img src={`/replay/${current.id}.jpg`} alt="本次检查的检测回放" /></div>
        <p className="replay-caption">{formatTime(current.ts)} · {current.risk}风险</p>
        <div className="replay-thumbs">{replays.map(item => <button className={item.id === current.id ? 'selected' : ''} key={item.id} onClick={() => setSelected(item.id)} aria-label={`查看${formatTime(item.ts)}的回放`}><img src={`/replay/${item.id}.jpg`} alt="" /></button>)}</div>
      </> : <div className="empty-card"><PlayCircleOutlineRounded sx={{ fontSize: 42 }} /><strong>暂无检查回放</strong><p>完成一次有检测结果的观察后，画面会出现在这里。</p><button onClick={() => onNavigate('home')}>返回首页</button></div>}
    </section>
  )
}

function Reminders({ user, replays, onNavigate }) {
  return <section className="sub-page"><h2>AI 提醒</h2><p className="sub-lead">根据本次观察结果，及时关注爱宠口腔变化。</p>
    <div className="reminder-card"><WarningAmberRounded sx={{ fontSize: 25 }} /><div><strong>实时观察提醒</strong><p>{displayBanner(user?.banner?.text) || '等待本次检查结果。'}</p></div></div>
    {replays.length ? replays.slice(0, 8).map(item => <div className="history-row" key={item.id}><span>{formatTime(item.ts)}</span><b>{item.risk}风险</b></div>) : <div className="empty-card compact"><NotificationsNoneRounded sx={{ fontSize: 37 }} /><strong>暂无历史提醒</strong><p>完成检查后，这里会显示相关记录。</p><button onClick={() => onNavigate('home')}>返回首页</button></div>}
  </section>
}

function Mine() {
  return <section className="sub-page"><h2>我的</h2><p className="sub-lead">这里是 PetOrb 的演示档案区域。</p>
    <div className="profile-card"><span className="profile-avatar"><PetsRounded sx={{ fontSize: 28 }} /></span><div><strong>演示宠物</strong><p>档案功能敬请期待</p></div></div>
    <div className="history-row"><span>检查记录</span><b>本次服务内回放</b></div><div className="history-row"><span>预约医生</span><b>敬请期待</b></div>
  </section>
}

export default function App() {
  const { user, replays, error } = useCheckData()
  const [tab, setTab] = useState('home')
  const [deviceOpen, setDeviceOpen] = useState(false)
  const [liveOpen, setLiveOpen] = useState(false)
  const hasResult = Boolean(user?.frames)
  const stale = !previewMode && hasResult && Date.now() - user.updated_ms > 5000
  const deviceLabel = previewMode || (hasResult && !stale) ? '设备已连接' : error ? '服务未连接' : '等待设备连接'
  const currentPage = useMemo(() => {
    if (tab === 'replay') return <Replay replays={replays} onNavigate={setTab} />
    if (tab === 'remind') return <Reminders user={user} replays={replays} onNavigate={setTab} />
    if (tab === 'mine') return <Mine />
    return <Home user={user} hasResult={hasResult} stale={stale} onNavigate={setTab} onOpenLive={() => setLiveOpen(true)} />
  }, [tab, user, replays, hasResult, stale])

  return <div className="app-shell">
    <header className="site-header">
      <div className="brand-row">
        <div className="brand"><span>PetOrb</span><EcoRounded className="brand-leaf" sx={{ fontSize: 16 }} /><p>家庭口腔观察</p></div>
        <button className="device-pill" onClick={() => setDeviceOpen(true)}><span className={`device-dot ${error ? 'offline' : ''}`} />{deviceLabel}<ChevronRightRounded sx={{ fontSize: 19 }} /></button>
      </div>
      <div className="tagline">用观察，守护它的笑容 <PetsRounded sx={{ fontSize: 20 }} /></div>
    </header>
    <main>{currentPage}</main>
    <nav className="bottom-nav" aria-label="主导航">{navItems.map(({ id, label, Icon }) => <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => { setTab(id); window.scrollTo({ top: 0, behavior: 'smooth' }) }}><Icon sx={{ fontSize: 26 }} /><span>{label}</span></button>)}</nav>
    {deviceOpen && <div className="modal-backdrop" role="presentation" onClick={() => setDeviceOpen(false)}><section className="device-modal" role="dialog" aria-modal="true" aria-label="设备状态" onClick={e => e.stopPropagation()}><button className="modal-close" onClick={() => setDeviceOpen(false)} aria-label="关闭"><CloseRounded /></button><WifiOffRounded sx={{ fontSize: 32, color: '#d8b56c' }} /><h2>{deviceLabel}</h2><p>请将 GO 3S 通过 Wi-Fi 连接手机，并在预览画面中开启“传到电脑检测”。电脑服务和 USB 调试也需要保持连接。</p><button className="modal-done" onClick={() => setDeviceOpen(false)}>知道了</button></section></div>}
    {liveOpen && <LiveWindow onClose={() => setLiveOpen(false)} />}
  </div>
}
