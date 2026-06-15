import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";
import { isPublicSignPath } from "./utils/publicSignRoute";

import "./tailwind.css";
import "./styles.css";
import "./styles/hq-stitch.css";
import "./styles/functional-eval-menu.css";
import "./styles/functional-eval-senior.css";
import "./styles/new-site-deployment-menu.css";

async function bootstrap() {
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);

  const auth = useAuthStore();
  const onPublicSignPage =
    typeof window !== "undefined" && isPublicSignPath(window.location.pathname);
  if (auth.token && !auth.user && !onPublicSignPage) {
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
