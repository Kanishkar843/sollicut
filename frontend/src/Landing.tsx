import { AudioLines, Film, Mic, Moon, Sparkles, Sun } from 'lucide-react'
import { FrostedFolderLookbook } from './components/ui/frosted-folder-lookbook'
import { useTheme } from './theme'

const sheets = [
  {
    image: '/lookbook/retail.png',
    alt: 'Boutique apparel and woven silk showcase card',
    title: 'Your collection',
    code: 'RETAIL',
    detail: 'From new arrivals to new customers',
  },
  {
    image: '/lookbook/florist.png',
    alt: 'Fresh flower garland and festive bouquet card',
    title: 'Your craft',
    code: 'FLORIST',
    detail: 'Made by you. Told in your voice.',
  },
  {
    image: '/lookbook/food.png',
    alt: 'Local food and homemade kitchen specials card',
    title: 'Your everyday',
    code: 'FOOD',
    detail: 'Give your next offer a story',
  },
  {
    image: '/lookbook/beauty.png',
    alt: 'Beauty studio and botanical care showcase card',
    title: 'Your next launch',
    code: 'BEAUTY',
    detail: 'A small product. A big impression.',
  },
]

export default function Landing() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="landing">
      <nav aria-label="Primary navigation">
        <a className="brand" href="#">
          <span className="brand-icon">
            <AudioLines size={20} />
          </span>
          SolliCut
        </a>
        <a href="#how">How it works</a>
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Switch to white & blue theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <a className="lime-button" href="#studio">
          Open studio
        </a>
      </nav>

      <section className="landing-hero">
        <span className="eyebrow">A VOICE-FIRST CREATIVE STUDIO</span>
        <h1>
          Your business.
          <br />
          Your voice.
          <br />
          <em>Your next big story.</em>
        </h1>
        <p>
          Turn your photos, clips and ideas into promotional videos.
          <br />
          Speak in Tamil, Tanglish or English. Make it yours.
        </p>
        <a className="lime-button" href="#studio">
          <Mic size={19} />
          Start creating
        </a>
        <span className="hero-note">Local voice editing. No API key required.</span>
      </section>

      <FrostedFolderLookbook
        title="YOUR NEXT CAMPAIGN"
        subtitle="Speak it. Cut it. Sell it."
        line="Tamil · Tanglish · English"
        footer="Ideas worth sharing"
        wordmark="SolliCut"
        sheets={sheets}
        tint={theme === 'light' ? '#2563eb' : '#d7ef41'}
        background={theme === 'light' ? '#f4f7fc' : '#0b0d0c'}
        height="min(640px, 78svh)"
        openLabel="Open your possibilities"
        closeLabel="Close collection"
      />

      <section className="landing-features" id="how">
        <article>
          <Film />
          <h2>Bring your media</h2>
          <p>Start with the photos, video clips and moments that make your shop, studio or kitchen yours.</p>
        </article>
        <article>
          <Mic />
          <h2>Say the edit</h2>
          <p>Describe duration, trim, music, zoom and offer text. Review what SolliCut understood and refine anytime.</p>
        </article>
        <article>
          <Sparkles />
          <h2>Make your next ad</h2>
          <p>Preview on a real timeline, undo safely and export 9:16 MP4. Optional Gemini cloud ads activate only with a server key.</p>
        </article>
      </section>

      <footer>
        <span>SolliCut · Speak it. Cut it. Sell it.</span>
        <a href="#studio">Create your first reel</a>
      </footer>
    </div>
  )
}
