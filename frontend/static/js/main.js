// frontend/static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const transcriptionDisplay = document.getElementById('transcriptionDisplay');
    const alertDisplay = document.getElementById('alertDisplay');
    const speakerTypeSelect = document.getElementById('speakerType');
    const uploadAudioBtn = document.getElementById('uploadAudio');
    const audioFileInput = document.getElementById('audioFileInput');
    const keywordListDiv = document.getElementById('keywordList');
    const newKeywordInput = document.getElementById('newKeywordInput');
    const newTalkingPointInput = document.getElementById('newTalkingPointInput');
    const addKeywordBtn = document.getElementById('addKeyword');

    let mediaRecorder;
    let audioChunks = [];
    let ws;
    let sessionId = generateSessionId(); // Unique ID for the session
    let keywords = []; // Store keywords fetched from backend

    // --- WebSocket Setup ---
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/audio/${sessionId}/`;
        console.log('Attempting to connect WebSocket to:', wsUrl);
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected successfully');
            ws.send(JSON.stringify({ type: 'set_speaker_type', speaker_type: speakerTypeSelect.value }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'transcription') {
                displayTranscription(data.data.text, data.data.speaker_type);
            } else if (data.type === 'alert') {
                displayAlert(data.data.keyword, data.data.talking_point, data.data.full_text, data.data.speaker_type);
            } else if (data.type === 'self_test_response') { // Added for self-test feedback
                console.log('Consumer self-test successful! Message:', data.data);
            }
        };

        ws.onclose = (event) => {
            console.log('WebSocket disconnected', event);
            if (!event.wasClean) {
                console.log('Attempting to reconnect WebSocket...');
                setTimeout(connectWebSocket, 3000);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            ws.close();
        };
    }

    // --- Audio Recording and Streaming ---
    startRecordingBtn.addEventListener('click', async () => {
        sessionId = generateSessionId();
        connectWebSocket();

        try {
            console.log('Requesting microphone access...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('Microphone access granted. Stream:', stream);

            // Explicitly specify the MIME type and codec for MediaRecorder
            // Use 'audio/webm;codecs=opus' as it's widely supported and efficient
            const options = { mimeType: 'audio/webm;codecs=opus' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                console.warn(`${options.mimeType} is not supported, trying default.`);
                // Fallback to default if not supported
                mediaRecorder = new MediaRecorder(stream);
            } else {
                mediaRecorder = new MediaRecorder(stream, options);
            }

            console.log('MediaRecorder created. State:', mediaRecorder.state);

            mediaRecorder.ondataavailable = (event) => {
                console.log('ondataavailable event fired. Data size:', event.data.size);
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(event.data);
                        console.log('Sent audio chunk to WebSocket. Chunk size:', event.data.size);
                    } else {
                        console.warn('WebSocket not open, could not send audio chunk.');
                    }
                } else {
                    console.log('ondataavailable event fired, but data size is 0.');
                }
            };

            mediaRecorder.onstop = () => {
                console.log('Recording stopped');
                audioChunks = [];
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
                const errorMessage = `MediaRecorder error: ${event.error.name} - ${event.error.message}`;
                console.error('Recording Error: ' + errorMessage); // Using console.error instead of alert
            };

            mediaRecorder.start(1000); // Start recording, collect data every 1 second
            console.log('MediaRecorder started. Current state:', mediaRecorder.state);

            startRecordingBtn.disabled = true;
            stopRecordingBtn.disabled = false;
            console.log('Recording started...');
            transcriptionDisplay.innerHTML = '<p class="text-gray-500">Recording started, transcription will appear here...</p>';
            alertDisplay.innerHTML = '<p class="text-gray-500">Alerts will appear here...</p>';

        } catch (error) {
            console.error('Error accessing microphone:', error);
            const errorMessage = 'Could not start recording. Please ensure microphone access is granted.';
            console.error('Microphone Access Error: ' + errorMessage); // Using console.error instead of alert
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
        }
    });

    stopRecordingBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            console.log('Stopping MediaRecorder...');
            mediaRecorder.stop();
            if (ws) {
                console.log('Closing WebSocket...');
                ws.close();
            }
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
            console.log('Recording stopped.');
        } else {
            console.log('MediaRecorder not in recording state, cannot stop.');
        }
    });

    speakerTypeSelect.addEventListener('change', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'set_speaker_type', speaker_type: speakerTypeSelect.value }));
            console.log('Sent speaker type update:', speakerTypeSelect.value);
        }
    });

    // --- Audio File Upload ---
    uploadAudioBtn.addEventListener('click', () => {
        audioFileInput.click();
    });

    audioFileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        console.log('Uploading audio file:', file.name, 'Type:', file.type);
        const formData = new FormData();
        formData.append('audio', file);
        formData.append('session_id', generateSessionId());
        formData.append('speaker_type', speakerTypeSelect.value);

        try {
            const response = await fetch('/api/upload-audio/', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Audio file uploaded successfully:', result);
                alertDisplay.innerHTML = `<p class="text-green-600">Audio file uploaded. Processing started for session: ${result.session_id}</p>`;
            } else {
                const error = await response.json();
                console.error('Audio file upload failed:', error);
                alertDisplay.innerHTML = `<p class="text-red-600">Error uploading audio: ${error.error}</p>`;
            }
        } catch (error) {
            console.error('Network error during audio upload:', error);
            alertDisplay.innerHTML = `<p class="text-red-600">Network error during upload.</p>`;
        }
    });

    // --- Transcription Display ---
    function displayTranscription(text, speakerType) {
        if (transcriptionDisplay.querySelector('p.text-gray-500')) {
            transcriptionDisplay.innerHTML = '';
        }

        const p = document.createElement('p');
        p.className = `mb-1 ${speakerType === 'prospect' ? 'text-indigo-700 font-semibold' : 'text-gray-700'}`;
        p.innerHTML = `<strong>${speakerType}:</strong> ${highlightKeywordsInText(text)}`;
        transcriptionDisplay.appendChild(p);
        transcriptionDisplay.scrollTop = transcriptionDisplay.scrollHeight;
        console.log('Displayed transcription:', text);
    }

    function highlightKeywordsInText(text) {
        let highlightedText = text;
        keywords.forEach(kw => {
            const regex = new RegExp(`(${kw.word})`, 'gi');
            highlightedText = highlightedText.replace(regex, `<span class="highlight">$1</span>`);
        });
        return highlightedText;
    }

    // --- Keyword Alerts ---
    function displayAlert(keyword, talkingPoint, fullText, speakerType) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert-box bg-yellow-100 border-l-4 border-yellow-500 text-yellow-800 p-3 mb-3 rounded-md shadow-sm';
        alertDiv.innerHTML = `
            <p class="font-bold">Keyword Detected: <span class="text-yellow-700">${keyword}</span> (from ${speakerType})</p>
            ${talkingPoint ? `<p class="text-sm mt-1"><strong>Talking Point:</strong> ${talkingPoint}</p>` : ''}
            <p class="text-xs text-gray-600 mt-2">"${fullText}"</p>
        `;
        alertDisplay.prepend(alertDiv);
        alertDiv.addEventListener('animationend', () => {
            alertDiv.remove();
        });
        console.log('Displayed alert for keyword:', keyword);
    }

    // --- Keyword Configuration ---
    async function loadKeywords() {
        try {
            const response = await fetch('/api/keywords/');
            if (response.ok) {
                keywords = await response.json();
                renderKeywords();
                console.log('Keywords loaded:', keywords);
            } else {
                console.error('Failed to load keywords:', await response.json());
            }
        } catch (error) {
            console.error('Network error loading keywords:', error);
        }
    }

    function renderKeywords() {
        keywordListDiv.innerHTML = '';
        keywords.forEach(kw => {
            const span = document.createElement('span');
            span.className = 'bg-gray-200 text-gray-800 text-sm px-3 py-1 rounded-full flex items-center gap-1';
            span.innerHTML = `
                ${kw.word}
                <button data-id="${kw.id}" class="delete-keyword-btn text-red-500 hover:text-red-700 ml-1 font-bold text-lg leading-none">&times;</button>
            `;
            keywordListDiv.appendChild(span);
        });
        attachDeleteKeywordListeners();
    }

    addKeywordBtn.addEventListener('click', async () => {
        const word = newKeywordInput.value.trim();
        const talkingPoint = newTalkingPointInput.value.trim();
        if (word) {
            try {
                const response = await fetch('/api/keywords/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ word: word, talking_point: talkingPoint, is_active: true }),
                });
                if (response.ok) {
                    const newKw = await response.json();
                    keywords.push(newKw);
                    renderKeywords();
                    newKeywordInput.value = '';
                    newTalkingPointInput.value = '';
                    console.log('Keyword added:', newKw);
                } else {
                    console.error('Failed to add keyword:', await response.json());
                }
            } catch (error) {
                console.error('Network error adding keyword:', error);
            }
        }
    });

    function attachDeleteKeywordListeners() {
        document.querySelectorAll('.delete-keyword-btn').forEach(button => {
            button.onclick = async (event) => {
                const keywordId = event.target.dataset.id;
                try {
                    const response = await fetch(`/api/keywords/${keywordId}/`, {
                        method: 'DELETE',
                    });
                    if (response.ok) {
                        keywords = keywords.filter(kw => kw.id !== parseInt(keywordId));
                        renderKeywords();
                        console.log('Keyword deleted:', keywordId);
                    } else {
                        console.error('Failed to delete keyword:', await response.json());
                    }
                } catch (error) {
                    console.error('Network error deleting keyword:', error);
                }
            };
        });
    }

    // --- Utility Functions ---
    function generateSessionId() {
        return 'session_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    }

    // Initial load
    loadKeywords();
});
