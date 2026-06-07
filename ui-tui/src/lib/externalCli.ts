import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

export interface LaunchResult {
  code: null | number
  error?: string
}

// For /setup slash command — launch the Python setup wizard.
// Resolves the python binary from env, defaults to 'python3'.
// The setup script is at tui_gateway/setup.py relative to HERMES_PYTHON_SRC_ROOT.
const resolveSetupBin = () => {
  const custom = process.env.SOCRATIC_SETUP_BIN?.trim()
  if (custom) return { bin: custom, args: [] as string[] }

  const python = process.env.HERMES_PYTHON || process.env.PYTHON || 'python3'
  return { bin: python, args: ['-m', 'tui_gateway.setup'] }
}

export const launchHermesCommand = (args: string[]): Promise<LaunchResult> =>
  new Promise(resolve => {
    const { bin, args: setupArgs } = resolveSetupBin()
    const child = spawn(bin, [...setupArgs, ...args], {
      stdio: 'inherit',
      cwd: process.env.HERMES_CWD || process.env.HERMES_PYTHON_SRC_ROOT || process.cwd(),
    })

    child.on('error', err => resolve({ code: null, error: err.message }))
    child.on('exit', code => resolve({ code }))
  })
