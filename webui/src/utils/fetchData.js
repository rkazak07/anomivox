import {ref} from 'vue';
import { useBasicStore } from '@/store/basic'

export function fetchData(url, data = {}) {
  const isDone = ref(false);
  const fetchResult = ref([]);

  // Auth token'ı header'a ekle
  const headers = { 'Content-Type': 'application/json' }
  try {
    const { token } = useBasicStore()
    if (token) headers['Authorization'] = token
  } catch (_) {}

  fetch(import.meta.env.VITE_APP_BASE_URL + url, {
    method: 'POST',
    headers,
    body: JSON.stringify(data)
  })
    .then(response => {
      const reader = response.body.getReader();
      return new ReadableStream({
        start(controller) {
          function push() {
            reader.read().then(({done, value}) => {
              if (done) {
                controller.close();
                isDone.value = true;
                return;
              }
              const decoder = new TextDecoder('utf-8');
              const resonseStr = decoder.decode(value);
              // console.log(resonseStr);
              try {
                const jsonObj = JSON.parse(resonseStr);
                fetchResult.value.push(jsonObj);
              } catch {
                const jsonArray = resonseStr.match(/{.*?}(?=({|$))/g);
                jsonArray.forEach(jsonStr => {
                  try {
                    const jsonObj = JSON.parse(jsonStr);
                    fetchResult.value.push(jsonObj);
                  } catch (e) {
                    console.error(e);
                  }
                });
              }
              controller.enqueue(value);
              push();
            });
          }

          push();
        }
      });
    })

  return {isDone, fetchResult};
}
