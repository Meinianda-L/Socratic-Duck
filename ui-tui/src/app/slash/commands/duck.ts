import type { SlashCommand } from '../types.js'

export const duckCommands: SlashCommand[] = [
  {
    help: 'list saved sessions',
    name: 'chats',
    run: (_arg, ctx) => {
      ctx.gateway.gw.request<{output?: string}>('slash.exec', {
        command: 'chats',
        session_id: ctx.sid || '',
      }).then(r => {
        if (ctx.stale()) return
        if (r?.output) ctx.transcript.sys(r.output)
      }).catch(() => {})
    },
  },
  {
    help: 'switch to chat by number',
    name: 'chat',
    run: (arg, ctx) => {
      const num = parseInt(arg, 10)
      if (isNaN(num)) return ctx.transcript.sys('Usage: /chat <number>')
      ctx.gateway.gw.request<{output?: string; target_session?: string}>('slash.exec', {
        command: `chat ${num}`,
        session_id: ctx.sid || '',
      }).then(r => {
        if (ctx.stale() || !r) return
        if (r.target_session) {
          ctx.transcript.sys(`Switching to session ${num}…`)
          ctx.session.activateLiveSession(r.target_session)
        } else {
          ctx.transcript.sys(r.output || 'Session not found')
        }
      }).catch(() => {})
    },
  },
  {
    help: 'rename current chat',
    name: 'rename',
    run: (arg, ctx) => {
      ctx.gateway.gw.request<{output?: string}>('slash.exec', {
        command: `rename ${arg}`,
        session_id: ctx.sid || '',
      }).then(r => {
        if (ctx.stale()) return
        if (r?.output) ctx.transcript.sys(r.output)
      }).catch(() => {})
    },
  },
  {
    help: 'show session info',
    name: 'stat',
    run: (_arg, ctx) => {
      ctx.gateway.gw.request<{output?: string}>('slash.exec', {
        command: 'stat',
        session_id: ctx.sid || '',
      }).then(r => {
        // stat sends session.info event directly
      }).catch(() => {})
    },
  },
]
