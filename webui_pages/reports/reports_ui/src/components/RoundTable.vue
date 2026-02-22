<template>
  <div class="c-flex-column c-align-items-center" style="padding: 20px;">
    <div>
      <img src="@/assets/dba_robot.webp">
    </div>

    <div class="c-flex-row c-justify-content-between" style="width: 100%; margin-top: 10px">
      <img src="@/assets/cpu_robot.webp">
      <img src="@/assets/mem_robot.webp">
      <img src="@/assets/io_robot.webp">
    </div>
    <div
      class="c-flex-column"
      style="width: 100%; margin-top: 10px; border-radius: 8px; border: 2px solid lightcoral;
          height: calc(100% - 220px);"
    >
      <span style="width: 100%; text-align: center; margin-top: 5px">Yuvarlak Masa Tartışması</span>
      <Chat :messages="messages" />
    </div>

    <div class="c-flex-row c-justify-content-left" style="width: 100%; margin-top: 10px">
      <img src="@/assets/dba_robot.webp" style="width: 30px; height: 30px;">
      <span style="color: #333333; margin-left: 5px; line-height: 20px">Ekibimiz bu anomali için ayrıntılı rapor oluşturdu, <span style="color: #007AFF">indir</span> butonuna tıklayarak görüntüleyebilirsiniz</span>
    </div>

  </div>
</template>

<script>

import Chat from '@/components/Chat'
export default {
  name: 'RoundTable',
  components: { Chat },
  data() {
    return {
      messages: [
        { sender: 'Chief DBA', content: { diagnose: 'Herkes düşüncelerini paylaştı, tartışmayı başlatın!' }, type: 'message', time: '2023-09-10 21:44:23' },
        { sender: 'CPU Agent', content: { diagnose: 'CPU açısından analiz edildiğinde XXX metriğinde sorun tespit edildi' }, type: 'message', time: '2023-09-10 21:44:23' }]
    }
  }
}
</script>

<style scoped>

</style>
