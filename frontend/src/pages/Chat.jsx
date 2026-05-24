import { useState, useRef, useEffect } from 'react'

const SUGGESTIONS = [
  "Quel est l'état de la flotte en ce moment ?",
  "Quels véhicules sont les plus à risque ?",
  "Y a-t-il des perturbations sur le réseau TC à Paris ou Lille ?",
  "Analyse les conditions météo et trafic actuels.",
  "Quelles livraisons nécessitent une attention immédiate ?",
  "Donne-moi un résumé opérationnel complet.",
]

const STORAGE_KEY = 'shamar-chat-history'
const INITIAL_MSG  = {
  role: 'assistant',
  content: "Bonjour ! Je suis Shamar, votre assistant IA pour la plateforme Smart Logistics.\n\nJe surveille en temps réel :\n- Votre flotte de 8 véhicules et les livraisons (France)\n- La météo pour toutes les villes de livraison\n- Le trafic routier et les transports en commun (métro, RER, bus, tram) à Paris et Lille\n\nComment puis-je vous aider ?",
}

function TypingDots() {
  return (
    <div className="chat-bubble assistant typing-bubble">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`chat-message-row ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="chat-avatar">
          <span>🧠</span>
        </div>
      )}
      <div className={`chat-bubble ${isUser ? 'user' : 'assistant'}`}>
        {msg.content.split('\n').map((line, i) => (
          <span key={i}>
            {line}
            {i < msg.content.split('\n').length - 1 && <br />}
          </span>
        ))}
      </div>
      {isUser && (
        <div className="chat-avatar user-avatar">
          <span>👤</span>
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      const parsed = saved ? JSON.parse(saved) : null
      return Array.isArray(parsed) && parsed.length > 0 ? parsed : [INITIAL_MSG]
    } catch {
      return [INITIAL_MSG]
    }
  })
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)
  const inputRef              = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  // Persistance localStorage (garde les 50 derniers messages)
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-50)))
    } catch {}
  }, [history])

  async function send(text) {
    const msg = text || input.trim()
    if (!msg || loading) return
    setInput('')

    const userMsg    = { role: 'user', content: msg }
    const newHistory = [...history, userMsg]
    setHistory(newHistory)
    setLoading(true)

    // Ajouter un message assistant vide comme placeholder streaming
    setHistory(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const res = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          history: newHistory.slice(0, -1),
        }),
      })

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') break
          try {
            const { token, error } = JSON.parse(data)
            if (error) {
              setHistory(prev => {
                const arr = [...prev]
                arr[arr.length - 1] = { ...arr[arr.length - 1], content: `Erreur : ${error}` }
                return arr
              })
            } else if (token) {
              setHistory(prev => {
                const arr = [...prev]
                arr[arr.length - 1] = {
                  ...arr[arr.length - 1],
                  content: arr[arr.length - 1].content + token,
                }
                return arr
              })
            }
          } catch {}
        }
      }
    } catch (e) {
      setHistory(prev => {
        const arr = [...prev]
        arr[arr.length - 1] = { role: 'assistant', content: `Erreur : ${e.message}` }
        return arr
      })
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat-layout">
      {/* ── Messages ── */}
      <div className="chat-messages">
        <div className="chat-messages-inner">
          {history.map((msg, i) => <Message key={i} msg={msg} />)}
          {loading && history[history.length - 1]?.content === '' && (
            <div className="chat-message-row assistant">
              <div className="chat-avatar"><span>🧠</span></div>
              <TypingDots />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Suggestions ── */}
      <div className="chat-suggestions">
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            className="suggestion-chip"
            onClick={() => send(s)}
            disabled={loading}
          >
            {s}
          </button>
        ))}
      </div>

      {/* ── Input ── */}
      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Posez votre question à Shamar… (Entrée pour envoyer)"
          rows={2}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={() => send()}
          disabled={loading || !input.trim()}
        >
          {loading ? '⏳' : '➤'}
        </button>
      </div>
    </div>
  )
}
