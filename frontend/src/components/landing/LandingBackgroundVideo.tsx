import { useEffect, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'

export const LANDING_VIDEO_SRC = '/videos/sollicut-background-loop.mp4'
export const LANDING_POSTER_SRC = '/videos/sollicut-background-poster.jpg'

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Full-bleed decorative background video scoped strictly to the Landing page.
 * Unmounts and releases its media resource whenever the user navigates to Studio.
 */
export default function LandingBackgroundVideo() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const [reducedMotion, setReducedMotion] = useState<boolean>(prefersReducedMotion)
  const [userPaused, setUserPaused] = useState(false)
  const userPausedRef = useRef(false)
  const [isPlaying, setIsPlaying] = useState(() => !prefersReducedMotion())
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    userPausedRef.current = userPaused
  }, [userPaused])

  // Listen to live OS prefers-reduced-motion changes
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => {
      const reduced = mq.matches
      setReducedMotion(reduced)
      if (reduced) {
        videoRef.current?.pause()
        setIsPlaying(false)
      }
    }
    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', onChange)
      return () => mq.removeEventListener('change', onChange)
    }
    mq.addListener?.(onChange)
    return () => mq.removeListener?.(onChange)
  }, [])

  // Start silent autoplay safely, handle visibility pause/resume, and release media on unmount
  useEffect(() => {
    const el = videoRef.current
    if (!el || reducedMotion || hasError) return

    let active = true
    el.defaultMuted = true
    el.muted = true

    const safePlay = () => {
      const target = videoRef.current
      if (!target) return
      const p = target.play?.()
      if (p && typeof p.then === 'function') {
        p.then(() => {
          if (active) setIsPlaying(true)
        }).catch(() => {
          if (active) setIsPlaying(false)
        })
      } else {
        setIsPlaying(true)
      }
    }

    if (!userPausedRef.current && !document.hidden) {
      safePlay()
    }

    const onVisibilityChange = () => {
      const target = videoRef.current
      if (!target) return
      if (document.hidden) {
        target.pause()
        setIsPlaying(false)
      } else if (!userPausedRef.current && !reducedMotion && !hasError) {
        safePlay()
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      active = false
      document.removeEventListener('visibilitychange', onVisibilityChange)
      el.pause()
      el.removeAttribute('src')
      if (typeof el.load === 'function') {
        el.load()
      }
    }
  }, [reducedMotion, hasError])

  function togglePlayback() {
    const el = videoRef.current
    if (!el || reducedMotion || hasError) return
    if (userPaused || !isPlaying) {
      userPausedRef.current = false
      setUserPaused(false)
      const p = el.play?.()
      if (p && typeof p.then === 'function') {
        p.then(() => setIsPlaying(true)).catch(() => setIsPlaying(false))
      } else {
        setIsPlaying(true)
      }
    } else {
      userPausedRef.current = true
      setUserPaused(true)
      el.pause()
      setIsPlaying(false)
    }
  }

  const pausedState = userPaused || !isPlaying

  return (
    <>
      <div className="landing-bg" aria-hidden="true">
        <div
          className="landing-bg-poster"
          style={{ backgroundImage: `url(${LANDING_POSTER_SRC})` }}
        />
        {!reducedMotion && !hasError && (
          <video
            ref={videoRef}
            className="landing-bg-video"
            src={LANDING_VIDEO_SRC}
            poster={LANDING_POSTER_SRC}
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
            aria-hidden="true"
            tabIndex={-1}
            disablePictureInPicture
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onError={() => {
              setHasError(true)
              setIsPlaying(false)
            }}
          />
        )}
        <div className="landing-bg-scrim" />
      </div>

      {!reducedMotion && !hasError && (
        <button
          type="button"
          className="landing-motion-toggle"
          onClick={togglePlayback}
          aria-label={pausedState ? 'Play background video' : 'Pause background video'}
          aria-pressed={pausedState}
          title={pausedState ? 'Play background video' : 'Pause background video'}
        >
          {pausedState ? <Play size={13} /> : <Pause size={13} />}
          <span>{pausedState ? 'Play bg' : 'Pause bg'}</span>
        </button>
      )}
    </>
  )
}
