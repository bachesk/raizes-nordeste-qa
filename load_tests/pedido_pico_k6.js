import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 200 },
    { duration: '3m', target: 500 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.005'],
  },
};

export default function () {
  const res = http.get('https://homolog.raizesdonordeste.local/api/v1/units/REC-01/menu');
  check(res, {
    'status 200': (r) => r.status === 200,
    'tempo abaixo de 2s': (r) => r.timings.duration < 2000,
  });
  sleep(1);
}
