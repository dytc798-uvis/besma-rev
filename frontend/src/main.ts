import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";
import { isPublicSignPath } from "./utils/publicSignRoute";
import { installBundleFreshnessGuard } from "./utils/textSafety";

import "./tailwind.css";
import "./styles.css";
import "./styles/hq-stitch.css";
import "./styles/functional-eval-menu.css";
import "./styles/functional-eval-senior.css";
import "./styles/new-site-deployment-menu.css";

async function bootstrap() {
  installBundleFreshnessGuard();
  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);

  const auth = useAuthStore();
  const onPublicSignPage =
    typeof window !== "undefined" && isPublicSignPath(window.location.pathname);
  if (auth.token && !auth.user && !onPublicSignPage) {
    void auth.bootstrapSession();
  }

  await router.isReady();
  app.mount("#app");
}

bootstrap();
