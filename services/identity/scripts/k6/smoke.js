// Smoke sintético de las APIs de Identity (no es un load test).
//
// Uso (dev):
//   k6 run services/identity/scripts/k6/smoke.js
// Uso (staging), con slugs públicos opcionales:
//   CAMAREROS_API_URL=https://camareros.siberia.solutions \
//   NEGOCIO_API_URL=https://negocio.siberia.solutions \
//   SLUG_WEB=<slug> SLUG_CARTA=<slug> \
//   k6 run services/identity/scripts/k6/smoke.js

import http from "k6/http";
import { check } from "k6";

const CAMAREROS = __ENV.CAMAREROS_API_URL || "http://localhost:8080";
const NEGOCIO = __ENV.NEGOCIO_API_URL || "http://localhost:8082";

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ["rate==0"],
    http_req_duration: ["p(95)<2000"],
  },
};

export default function () {
  check(http.get(`${CAMAREROS}/health`), {
    "camareros /health 200": (r) => r.status === 200,
  });
  check(http.get(`${NEGOCIO}/health`), {
    "negocio /health 200": (r) => r.status === 200,
  });
  check(http.get(`${CAMAREROS}/v1/meta`), {
    "camareros /v1/meta 200": (r) => r.status === 200,
  });
  check(http.get(`${NEGOCIO}/v1/meta`), {
    "negocio /v1/meta 200": (r) => r.status === 200,
  });

  const slugWeb = __ENV.SLUG_WEB || __ENV.SLUG_FICHA;
  if (slugWeb) {
    check(http.get(`${NEGOCIO}/v1/negocio/web?slug=${slugWeb}`), {
      "web pública 200": (r) => r.status === 200,
    });
  }

  const slugCarta = __ENV.SLUG_CARTA;
  if (slugCarta) {
    check(http.get(`${NEGOCIO}/v1/negocio/carta?slug=${slugCarta}`), {
      "carta pública 200": (r) => r.status === 200,
    });
  }
}
