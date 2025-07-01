// DreamCall WebRTC logic
let ws, peer, stream;
let myId = "", calleeId = "";
let isMuted = false;
let isCaller = false;
let callStartTime, callTimerInterval;

function register() {
  myId = document.getElementById("username").value.trim();
  if (!myId) return alert("Enter a valid username.");

  // ws = new WebSocket("ws://localhost:5000/ws");
  ws = new WebSocket("wss://vibes1.onrender.com/ws");


  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "register", user: myId }));
    document.getElementById("login").style.display = "none";
    document.getElementById("call-ui").style.display = "block";
  };

  ws.onmessage = async (e) => {
    const msg = JSON.parse(e.data);

    switch (msg.type) {
      case "incoming_call":
        calleeId = msg.from;
        document.getElementById("caller").innerText = calleeId;
        document.getElementById("ringing").style.display = "block";
        break;

      case "call_failed":
        alert("❌ " + msg.reason);
        break;

      case "call_accepted":
        isCaller = true;
        startWebRTC(true);
        break;

      case "call_rejected":
        alert("Call was rejected.");
        break;

      case "signal":
        await handleSignal(msg.data);
        break;

      case "dream":
        addSlide(msg.image, msg.text);
        break;

      case "summary":
        try {
          const summaryBox = document.getElementById("call-summary");
          const summaryText = document.getElementById("summary-text");
          const followupList = document.getElementById("followups-list");

          const parsed = JSON.parse(msg.text);
          summaryText.innerText = parsed.Summary || "No summary available.";
          followupList.innerHTML = "";
          if (parsed["Follow-up Suggestions"]) {
            parsed["Follow-up Suggestions"].forEach(item => {
              const li = document.createElement("li");
              li.textContent = item;
              followupList.appendChild(li);
            });
          }
          summaryBox.style.display = "block";
        } catch (e) {
          console.error("Failed to parse summary:", e);
        }
        break;

      case "ended_by_peer":
        cleanupCallUI();
        alert("Call ended by peer.");
        break;

      case "call_ended":
        cleanupCallUI();
        break;
    }
  };
}

function makeCall() {
  calleeId = document.getElementById("callee").value.trim();
  if (!calleeId) return alert("Enter callee username.");
  ws.send(JSON.stringify({ type: "call", from: myId, to: calleeId }));
}

function acceptCall() {
  document.getElementById("ringing").style.display = "none";
  ws.send(JSON.stringify({ type: "accept", from: myId, to: calleeId }));
  isCaller = false;
  startWebRTC(false);
}

function rejectCall() {
  document.getElementById("ringing").style.display = "none";
  ws.send(JSON.stringify({ type: "reject", to: calleeId }));
}

function endCall() {
  
  ws.send(JSON.stringify({ type: "end", from: myId, to: calleeId }));
  if (peer) peer.close();
  cleanupCallUI();
}

function cleanupCallUI() {
  document.getElementById("in-call").style.display = "none";
  clearInterval(callTimerInterval);
  const remoteAudio = document.getElementById("remoteAudio");
  if (remoteAudio) remoteAudio.remove();
  stream?.getTracks().forEach(t => t.stop());
  stream = null;
  peer = null;
}

document.getElementById("muteButton").addEventListener("click", () => {
  if (!stream) return;
  const audioTrack = stream.getAudioTracks()[0];
  isMuted = !isMuted;
  audioTrack.enabled = !isMuted;
  document.getElementById("muteButton").textContent = isMuted ? "🎙️ Unmute" : "🔇 Mute";
});

function startCallTimer() {
  callStartTime = Date.now();
  callTimerInterval = setInterval(() => {
    const elapsed = Date.now() - callStartTime;
    const mins = Math.floor(elapsed / 60000).toString().padStart(2, '0');
    const secs = Math.floor((elapsed % 60000) / 1000).toString().padStart(2, '0');
    document.getElementById("inCallWith").innerText = `${calleeId} (${mins}:${secs})`;
  }, 1000);
}

function setupMicLevelAnimation(stream) {
  const audioCtx = new AudioContext();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  const dataArray = new Uint8Array(analyser.frequencyBinCount);

  const animate = () => {
    analyser.getByteFrequencyData(dataArray);
    const avg = dataArray.reduce((a, b) => a + b) / dataArray.length;
    const micButton = document.getElementById("muteButton");
    micButton.style.boxShadow = avg > 20 && !isMuted ? "0 0 10px 4px #f59e0b" : "none";
    requestAnimationFrame(animate);
  };
  animate();
}

async function startWebRTC(caller) {
  document.getElementById("inCallWith").innerText = calleeId;
  document.getElementById("in-call").style.display = "block";

  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
  });

  setupMicLevelAnimation(stream);
  startCallTimer();

  peer = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
  });

  stream.getTracks().forEach(track => peer.addTrack(track, stream));

  peer.onicecandidate = e => {
    if (e.candidate) {
      ws.send(JSON.stringify({
        type: "signal",
        from: myId,
        to: calleeId,
        data: { type: "candidate", candidate: e.candidate }
      }));
    }
  };

  peer.ontrack = e => {
    if (e.track.kind === 'audio') {
      const remoteStream = e.streams[0];

      if (!document.getElementById("remoteAudio")) {
        const audio = document.createElement("audio");
        audio.id = "remoteAudio";
        audio.srcObject = remoteStream;
        audio.autoplay = true;
        audio.playsInline = true;
        document.body.appendChild(audio);
      }

      if (!isCaller) {
        let mediaRecorder;
        let audioChunks = [];

        mediaRecorder = new MediaRecorder(remoteStream, { mimeType: "audio/webm" });

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
          const blob = new Blob(audioChunks, { type: "audio/webm" });
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(blob);
          }
          audioChunks = [];
        };

        mediaRecorder.start();

        setInterval(() => {
          if (mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            mediaRecorder.start();
          }
        }, 2000);
      }
    }
  };

  if (caller) {
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    ws.send(JSON.stringify({
      type: "signal",
      from: myId,
      to: calleeId,
      data: { type: "offer", offer }
    }));
  }
}

async function handleSignal(data) {
  if (data.type === "offer") {
    await peer.setRemoteDescription(new RTCSessionDescription(data.offer));
    const answer = await peer.createAnswer();
    await peer.setLocalDescription(answer);
    ws.send(JSON.stringify({
      type: "signal",
      from: myId,
      to: calleeId,
      data: { type: "answer", answer }
    }));
  } else if (data.type === "answer") {
    await peer.setRemoteDescription(new RTCSessionDescription(data.answer));
  } else if (data.type === "candidate") {
    await peer.addIceCandidate(new RTCIceCandidate(data.candidate));
  }
}

function addSlide(image, text) {
  const board = document.getElementById("dreamboard");

  // Clear previous content
  board.innerHTML = "";

  // Create new dream slide
  const slide = document.createElement("div");
  slide.className = "dream fade-in";

  // Only show the heading and image (ignore text completely)
  slide.innerHTML = `
    <h2 style="text-align:center; margin-bottom: 10px;">Dreamboard</h2>
    <img src="${image}" alt="dream" style="max-width:100%; border-radius: 10px;" />
  `;

  board.appendChild(slide);
  board.scrollTo({ top: 0, behavior: "smooth" });
}


