import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";

import "./tailwind.css";
import "./styles.css";
import "./styles/hq-stitch.css";

async function bootstrap() {
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);

  const auth = useAuthStore();
  if (auth.token && !auth.user) {
    try {
      await auth.loadMe();
    } catch {
      auth.logout();
    }
  }

  app.use(router);
  await router.isReady();
  app.mount("#app");
}

bootstrap();
