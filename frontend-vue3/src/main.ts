import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import './styles/tailwind.css'
import './styles/globals.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        // Fix P1-2: Limit retry to 1 with fixed 1s delay instead of exponential backoff
        retry: 1,
        retryDelay: 1000,
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
    },
  },
})

app.mount('#app')
