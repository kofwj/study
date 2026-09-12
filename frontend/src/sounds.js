// 音效管理系统
class SoundManager {
  constructor() {
    this.sounds = {}
    this.broken = new Set() // 加载失败（404 等）的音效，play 返回 false 让调用方降级到 beep
    this.ctx = null // AudioContext 单例，移动端 Safari 有数量限制
    this.enabled = localStorage.getItem('soundEnabled') !== 'false'
    this.volume = parseFloat(localStorage.getItem('soundVolume') || '0.5')
    this.tested = false
  }

  // 预加载音效
  preload(name, url) {
    if (!this.sounds[name]) {
      const audio = new Audio(url)
      audio.preload = 'auto'
      audio.volume = this.volume
      audio.addEventListener('error', () => {
        this.broken.add(name)
        delete this.sounds[name]
      })
      this.sounds[name] = audio
    }
  }

  // 播放音效；不可用时返回 false，调用方应降级到 beep
  play(name, volume = null) {
    if (!this.enabled) return false

    const sound = this.sounds[name]
    if (!sound) {
      if (!this.broken.has(name)) console.warn(`Sound "${name}" not found`)
      return false
    }

    try {
      sound.currentTime = 0
      sound.volume = volume !== null ? volume : this.volume
      const playPromise = sound.play()

      if (playPromise !== undefined) {
        playPromise.catch(err => {
          // 自动播放被浏览器阻止，静默失败
          console.debug('Sound play blocked:', err)
        })
      }
      return true
    } catch (err) {
      console.error('Sound play error:', err)
      return false
    }
  }

  _ctx() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext
      if (!AC) return null
      this.ctx = new AC()
    }
    if (this.ctx.state === 'suspended') this.ctx.resume().catch(() => {})
    return this.ctx
  }

  // 使用 Web Audio API 生成简单音效（备用方案，无需外部文件）
  beep(frequency = 800, duration = 150, type = 'sine') {
    if (!this.enabled) return

    try {
      const ctx = this._ctx()
      if (!ctx) return
      const oscillator = ctx.createOscillator()
      const gain = ctx.createGain()

      oscillator.connect(gain)
      gain.connect(ctx.destination)

      oscillator.frequency.value = frequency
      oscillator.type = type
      gain.gain.value = this.volume * 0.3

      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + duration / 1000)
    } catch (err) {
      console.debug('Web Audio not supported')
    }
  }

  setEnabled(enabled) {
    this.enabled = enabled
    localStorage.setItem('soundEnabled', enabled)
  }

  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume))
    localStorage.setItem('soundVolume', this.volume)
    Object.values(this.sounds).forEach(sound => {
      sound.volume = this.volume
    })
  }
}

export const soundManager = new SoundManager()

// 预加载所有音效（文件缺失时 play 返回 false，自动降级到下面的合成音效）
soundManager.preload('complete', '/sounds/complete.mp3')
soundManager.preload('coin', '/sounds/coin.mp3')
soundManager.preload('levelup', '/sounds/levelup.mp3')
soundManager.preload('evolve', '/sounds/evolve.mp3')

// 导出便捷方法
export function playSound(name) {
  return soundManager.play(name)
}

// 导出合成音效（无需外部文件的备用方案）
export function playCompleteBeep() {
  soundManager.beep(880, 100, 'sine')
  setTimeout(() => soundManager.beep(1046, 120, 'sine'), 120)
}

export function playCoinBeep() {
  soundManager.beep(659, 80, 'square')
}

export function playLevelUpBeep() {
  soundManager.beep(523, 100, 'square')
  setTimeout(() => soundManager.beep(659, 100, 'square'), 120)
  setTimeout(() => soundManager.beep(784, 150, 'square'), 240)
}

export function playEvolveBeep() {
  soundManager.beep(440, 80, 'sine')
  setTimeout(() => soundManager.beep(554, 80, 'sine'), 100)
  setTimeout(() => soundManager.beep(659, 80, 'sine'), 200)
  setTimeout(() => soundManager.beep(880, 120, 'sine'), 300)
}
