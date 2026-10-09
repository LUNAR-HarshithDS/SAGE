import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

const messagesEl = document.getElementById('messages');
const thinkingBox = document.getElementById('thinking-box');
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-size');
const metricsEl = document.getElementById('metrics');

let currentAssistantBubble = null;
let currentThinkingText = '';
let sending = false;

function addBubble(role, text) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

listen('sage-stream', (event) => {
  const e = event.payload;
  switch (e.type) {
    case 'thinking_started':
      thinkingBox.classList.remove('hidden', 'collapsed');
      thinkingBox.textContent = '';
      currentThinkingText = '';
      break;

    case 'thinking_finished':
      thinkingBox.classList.add('collapsed');
      break;

    case 'token':
      if (e.thinking) {
        currentThinkingText += e.text;
        thinkingBox.textContent = currentThinkingText;
        thinkingBox.scrollTop = thinkingBox.scrollHeight;
      } else {
        if (!currentAssistantBubble) {
          currentAssistantBubble = addBubble('assistant', '');
        }
        currentAssistantBubble.textContent += e.text;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
      break;

    case 'complete':
      metricsEl.textContent = `${e.elapsed_secs.toFixed(1)}s · ${e.tokens_per_sec.toFixed(1)} tok/s`;
      currentAssistantBubble?.classList.add('done');
      currentAssistantBubble = null;
      sending = false;
      break;

    case 'error':
      addBubble('error', e.message);
      currentAssistantBubble = null;
      sending = false;
      break;
  }
});

async function send() {
  const text = input.value.trim();
  if (!text || sending) return;
  sending = true;
  input.value = '';
  addBubble('user', text);

  try {
    await invoke('send_message', {
      req: { message: text, model_size: modelSelect.value },
    });
  } catch (err) {
    addBubble('error', String(err));
    sending = false;
  }
}

sendBtn.addEventListener('click', send);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') send();
});

// Surface a basic hardware-suitability notice on launch. Phase 2 will move
// this into the proper status/orb UI instead of a plain system bubble.
invoke('check_environment').then((report) => {
  console.log('hardware report', report);
  if (report.fits.recommended === 'none') {
    addBubble(
      'system',
      'Heads up: this machine may struggle even with the smallest Sage model.'
    );
  } else {
    addBubble('system', `Detected hardware suggests the ${report.fits.recommended} model as a good default.`);
  }
});
