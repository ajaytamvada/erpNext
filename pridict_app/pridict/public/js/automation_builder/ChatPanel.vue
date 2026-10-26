<template>
	<section class="ab-chat" :class="{ collapsed: !chat.open }">
		<header class="ab-chat-head">
			<button type="button" class="ab-chat-toggle" @click="chat.open = !chat.open">
				<span class="ab-chat-caret">{{ chat.open ? "▾" : "▸" }}</span>
				{{ __("Build with AI") }}
			</button>
			<span v-if="chat.working" class="ab-chat-working">{{ __("Thinking…") }}</span>
		</header>
		<template v-if="chat.open">
			<div ref="list" class="ab-chat-list">
				<div v-if="!chat.messages.length" class="ab-chat-empty">
					<p>{{ __("Describe what should happen, and the architect builds it on the canvas below. For example:") }}</p>
					<button v-for="example in examples" :key="example" type="button" class="ab-chat-example" :disabled="!canSend" @click="send(example)">
						{{ example }}
					</button>
				</div>
				<div v-for="(message, index) in chat.messages" :key="index" class="ab-chat-msg" :class="[message.role, message.kind]">
					<div class="ab-chat-bubble">{{ message.content }}</div>
					<div v-if="message.choices && index === lastIndex && !chat.working" class="ab-chat-choices">
						<button v-for="choice in message.choices" :key="choice" type="button" class="btn btn-xs btn-default" :disabled="!canSend" @click="send(choice)">
							{{ choice }}
						</button>
					</div>
				</div>
				<div v-if="chat.working" class="ab-chat-msg assistant">
					<div class="ab-chat-bubble ab-chat-dots"><span></span><span></span><span></span></div>
				</div>
			</div>
			<div v-if="!chat.model" class="ab-chat-note">
				{{ __("No AI model is set for the architect. An administrator can choose one in Automation Settings.") }}
			</div>
			<form v-else-if="store.canEdit.value" class="ab-chat-form" @submit.prevent="send(draft)">
				<div v-if="chat.focus" class="ab-chat-focus">
					{{ __("About: {0}", [focusLabel]) }}
					<button type="button" class="btn btn-xs btn-link" :title="__('Ask about the whole automation')" @click="chat.focus = null">×</button>
				</div>
				<textarea
					ref="input"
					v-model="draft"
					class="form-control"
					rows="2"
					:placeholder="chat.messages.length ? __('Describe a change…') : __('Describe your automation…')"
					:disabled="chat.working"
					@keydown.enter.exact.prevent="send(draft)"
				></textarea>
				<button type="submit" class="btn btn-primary btn-sm" :disabled="!canSend || !draft.trim()">{{ __("Send") }}</button>
			</form>
		</template>
	</section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps({ store: Object });
const store = props.store;
const chat = store.state.chat;
const draft = ref("");
const list = ref(null);
const input = ref(null);

const examples = [
	__("When a new Supplier is created, email them our onboarding checklist and assign a check to the purchase team."),
	__("Every Monday at 9:00, email the purchase manager a list of purchase orders pending receipt for more than 14 days."),
	__("When a Sales Order over 5 lakh is submitted, notify the Sales Manager and add a comment on the order."),
];

const lastIndex = computed(() => chat.messages.length - 1);
const canSend = computed(() => store.canEdit.value && chat.model && !chat.working && !chat.sending);
const focusLabel = computed(() => {
	const node = chat.focus && store.nodeById(chat.focus);
	return node ? node.label || node.id : chat.focus;
});

async function send(text) {
	text = (text || "").trim();
	if (!text || !canSend.value) return;
	draft.value = "";
	await store.sendChat(text);
}

function scrollDown() {
	nextTick(() => {
		if (list.value) list.value.scrollTop = list.value.scrollHeight;
	});
}

watch(() => [chat.messages.length, chat.working], scrollDown);
watch(
	() => chat.focus,
	(focus) => focus && nextTick(() => input.value?.focus())
);
</script>

<style>
.ab-chat {
	display: flex;
	flex-direction: column;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-lg);
	background: var(--card-bg);
	max-height: 320px;
	flex: none;
}
.ab-chat.collapsed {
	max-height: none;
}
.ab-chat-head {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 6px 12px;
	border-bottom: 1px solid var(--border-color);
}
.ab-chat.collapsed .ab-chat-head {
	border-bottom: 0;
}
.ab-chat-toggle {
	border: 0;
	background: none;
	padding: 0;
	font-weight: 600;
}
.ab-chat-caret {
	display: inline-block;
	width: 14px;
	color: var(--text-muted);
}
.ab-chat-working {
	font-size: var(--text-xs);
	color: var(--text-muted);
}
.ab-chat-list {
	flex: 1;
	overflow-y: auto;
	padding: 8px 12px;
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-height: 60px;
}
.ab-chat-empty p {
	color: var(--text-muted);
	font-size: var(--text-sm);
	margin-bottom: 6px;
}
.ab-chat-example {
	display: block;
	width: 100%;
	text-align: left;
	border: 1px dashed var(--border-color);
	background: none;
	border-radius: var(--border-radius);
	padding: 4px 8px;
	margin-bottom: 4px;
	font-size: var(--text-sm);
	color: var(--text-color);
}
.ab-chat-example:hover:not(:disabled) {
	border-color: var(--blue-400);
}
.ab-chat-msg {
	display: flex;
	flex-direction: column;
	max-width: 85%;
}
.ab-chat-msg.user {
	align-self: flex-end;
	align-items: flex-end;
}
.ab-chat-msg.assistant {
	align-self: flex-start;
}
.ab-chat-bubble {
	padding: 6px 10px;
	border-radius: 10px;
	white-space: pre-wrap;
	font-size: var(--text-sm);
	line-height: 1.45;
}
.ab-chat-msg.user .ab-chat-bubble {
	background: var(--bg-blue);
	color: var(--text-on-blue);
}
.ab-chat-msg.assistant .ab-chat-bubble {
	background: var(--subtle-fg);
	color: var(--text-color);
}
.ab-chat-msg.error .ab-chat-bubble {
	background: var(--bg-red);
	color: var(--text-on-red);
}
.ab-chat-choices {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
	margin-top: 4px;
}
.ab-chat-dots span {
	display: inline-block;
	width: 6px;
	height: 6px;
	margin: 0 2px;
	border-radius: 50%;
	background: var(--gray-500);
	animation: ab-dot 1.2s infinite ease-in-out;
}
.ab-chat-dots span:nth-child(2) {
	animation-delay: 0.2s;
}
.ab-chat-dots span:nth-child(3) {
	animation-delay: 0.4s;
}
@keyframes ab-dot {
	0%,
	80%,
	100% {
		opacity: 0.3;
	}
	40% {
		opacity: 1;
	}
}
.ab-chat-form {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	align-items: flex-end;
	padding: 8px 12px;
	border-top: 1px solid var(--border-color);
}
.ab-chat-form textarea.form-control {
	flex: 1;
	resize: none;
	font-size: var(--text-sm);
	height: 56px;
	min-height: 56px;
}
.ab-chat-focus {
	width: 100%;
	font-size: var(--text-xs);
	color: var(--text-muted);
}
.ab-chat-note {
	padding: 8px 12px;
	font-size: var(--text-sm);
	color: var(--text-muted);
}
</style>
