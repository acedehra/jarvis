import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/jarvis/',
  title: 'J.A.R.V.I.S.',
  description: 'Autonomous Personal AI Operating System engineered with LangGraph, FastAPI, Next.js 16, and PostgreSQL',
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: true,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/jarvis/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#06b6d4' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:title', content: 'J.A.R.V.I.S. Documentation' }],
    ['meta', { name: 'og:description', content: 'Autonomous Personal AI Operating System' }]
  ],

  themeConfig: {
    siteTitle: 'J.A.R.V.I.S.',
    logo: {
      text: '🤖'
    },
    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Architecture & Core', link: '/core/langgraph-agent' },
      { text: 'Integrations', link: '/integrations/telegram-bot' },
      { text: 'Roadmap', link: '/roadmap/feature-roadmap' },
      {
        text: 'v2.0',
        items: [
          { text: 'Changelog & Roadmap', link: '/roadmap/feature-roadmap' },
          { text: 'GitHub Repository', link: 'https://github.com/acedehra/jarvis' }
        ]
      }
    ],

    sidebar: [
      {
        text: '🚀 Quick Start',
        collapsed: false,
        items: [
          { text: 'Getting Started', link: '/guide/getting-started' },
          { text: 'System Architecture', link: '/guide/architecture' },
          { text: 'Configuration (.env)', link: '/guide/configuration' },
          { text: 'Docker & Production', link: '/guide/docker-deployment' }
        ]
      },
      {
        text: '🧠 Core Architecture',
        collapsed: false,
        items: [
          { text: 'LangGraph State Machine', link: '/core/langgraph-agent' },
          { text: 'Dual-Layer Memory', link: '/core/dual-layer-memory' },
          { text: 'Dynamic MCP Runtime', link: '/core/mcp-runtime' },
          { text: 'HITL Safety Gate', link: '/core/hitl-safety' },
          { text: 'Deterministic SQL Analytics', link: '/core/sql-analytics' }
        ]
      },
      {
        text: '🔌 Integrations',
        collapsed: false,
        items: [
          { text: 'Telegram Gateway', link: '/integrations/telegram-bot' },
          { text: 'Next.js 16 Web Dashboard', link: '/integrations/web-dashboard' },
          { text: 'Kokoro TTS & Voice', link: '/integrations/kokoro-tts' },
          { text: 'Google Calendar Sync', link: '/integrations/google-calendar' }
        ]
      },
      {
        text: '🔮 Vision & Strategy',
        collapsed: false,
        items: [
          { text: 'J.A.R.V.I.S. 2.0 Roadmap', link: '/roadmap/feature-roadmap' }
        ]
      }
    ],

    search: {
      provider: 'local'
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/acedehra/jarvis' }
    ],

    editLink: {
      pattern: 'https://github.com/acedehra/jarvis/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    },

    footer: {
      message: 'Autonomous Personal AI Operating System — Built with LangGraph, FastAPI & Next.js',
      copyright: 'Released under the MIT License.'
    }
  }
})
