document.addEventListener('DOMContentLoaded', () => {
    
    // Tab Switching
    const tabs = document.querySelectorAll('.tab');
    const sections = document.querySelectorAll('.tab-content');
    
    if(tabs.length > 0) {
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.dataset.target;
                
                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Update active section
                sections.forEach(sec => {
                    if(sec.id === target) {
                        sec.style.display = 'block';
                        sec.classList.add('animate-enter');
                    } else {
                        sec.style.display = 'none';
                        sec.classList.remove('animate-enter');
                    }
                });
            });
        });
    }

    // Manual Verification Form
    const manualForm = document.getElementById('manual-form');
    if(manualForm) {
        manualForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const certData = {
                cert_number: document.getElementById('cert_number').value,
                student_name: document.getElementById('student_name').value,
                institution: document.getElementById('institution').value
            };
            
            showLoader();
            
            try {
                const response = await fetch('/api/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(certData)
                });
                const result = await response.json();
                displayResult(result);
            } catch (error) {
                console.error("Verification failed", error);
            } finally {
                hideLoader();
            }
        });
    }

    // File Upload Zone
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-upload');
    
    if(uploadZone && fileInput) {
        uploadZone.addEventListener('click', () => fileInput.click());
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => uploadZone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => uploadZone.classList.remove('dragover'), false);
        });

        uploadZone.addEventListener('drop', handleDrop, false);
        
        fileInput.addEventListener('change', (e) => {
            if(e.target.files.length) {
                handleFiles(e.target.files);
            }
        });
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
    
    function handleFiles(files) {
        const file = files[0];
        uploadFile(file);
    }
    
    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('document', file);
        
        showLoader();
        
        try {
            const response = await fetch('/api/verify_upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            displayResult(result);
        } catch (error) {
            console.error("Upload failed", error);
        } finally {
            hideLoader();
        }
    }

    // UI Helpers
    function showLoader() {
        const btn = document.querySelector('button[type="submit"]');
        if(btn) {
             btn.dataset.originalText = btn.innerHTML;
             btn.innerHTML = '<span class="loader"></span> Processing...';
             btn.disabled = true;
        }
    }

    function hideLoader() {
        const btn = document.querySelector('button[type="submit"]');
        if(btn && btn.dataset.originalText) {
             btn.innerHTML = btn.dataset.originalText;
             btn.disabled = false;
        }
    }

    function displayResult(result) {
        const rb = document.getElementById('result-box');
        const st = document.getElementById('result-status-text');
        const msg = document.getElementById('result-message');
        
        rb.classList.remove('verified', 'not-verified', 'show');
        
        if(result.status === 'Verified') {
            rb.classList.add('verified');
        } else {
            rb.classList.add('not-verified');
        }
        
        st.innerText = result.status;
        msg.innerText = result.message;
        
        if(result.cert_details) {
             msg.innerHTML += `<br><br><strong>Name:</strong> ${result.cert_details.student_name} <br><strong>Institution:</strong> ${result.cert_details.institution} <br><strong>Issued:</strong> ${result.cert_details.issue_date}`;
        }

        const cryptoEl = document.getElementById('result-crypto');
        if(cryptoEl && result.crypto_hash) {
             cryptoEl.innerHTML = `<i class="fa-solid fa-link"></i> Blockchain TX Proof<br>Block ID: <strong>${result.block_id}</strong><br>Hash: <strong>${result.crypto_hash}</strong>`;
             cryptoEl.style.display = 'block';
        } else if (cryptoEl) {
             cryptoEl.style.display = 'none';
        }
        
        rb.classList.add('show');
        
        // Optionally auto-reload page after few seconds to update history feed
        setTimeout(() => location.reload(), 5000);
    }

    // Load Analytics
    const analyticsTab = document.querySelector('.tab[data-target="analytics-section"]');
    if (analyticsTab) {
         analyticsTab.addEventListener('click', loadAnalytics);
    }

    let chartsLoaded = false;
    async function loadAnalytics() {
         if (chartsLoaded) return;
         try {
             const res = await fetch('/api/analytics');
             const data = await res.json();
             
             // Draw Ratio Chart
             const ctxRatio = document.getElementById('ratioChart');
             if (ctxRatio && window.Chart) {
                  new Chart(ctxRatio, {
                       type: 'doughnut',
                       data: {
                            labels: ['Verified', 'Tampered / Invalid'],
                            datasets: [{
                                 data: [data.verified, data.tampered],
                                 backgroundColor: ['#10B981', '#EF4444'],
                                 borderWidth: 0
                            }]
                       },
                       options: { color: '#F8FAFC', plugins: { legend: { labels: { color: '#F8FAFC' } } } }
                  });
             }

             // Draw Activity Chart (Mocked time series based on total)
             const ctxActivity = document.getElementById('activityChart');
             if (ctxActivity && window.Chart) {
                  new Chart(ctxActivity, {
                       type: 'bar',
                       data: {
                            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                            datasets: [{
                                 label: 'Scans',
                                 data: [0, 1, 0, 3, data.total, 0, 0], // simplified mock trends
                                 backgroundColor: '#4F46E5',
                                 borderRadius: 4
                            }]
                       },
                       options: { 
                           color: '#F8FAFC', 
                           plugins: { legend: { labels: { color: '#F8FAFC' } } },
                           scales: { 
                               y: { beginAtZero: true, ticks: { color: '#94A3B8' } }, 
                               x: { ticks: { color: '#94A3B8' } } 
                           } 
                       }
                  });
             }

             chartsLoaded = true;
         } catch(e) { console.error('Analytics load error', e); }
    }
});

// Smart Scholar Chat Logic (Global)
function toggleChat() {
    const body = document.getElementById('scholar-body');
    if (body.style.display === 'none' || !body.style.display) {
         body.style.display = 'flex';
    } else {
         body.style.display = 'none';
    }
}

function handleChat(e) {
    if (e.key === 'Enter') { sendChat(); }
}

function sendChat() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;

    addChatMessage(msg, 'user');
    input.value = '';

    // Simple bot logic
    setTimeout(() => {
         let response = "I'm your AI assistant! Try asking me about 'watermarks', 'blockchain', or 'tampering'.";
         const lower = msg.toLowerCase();
         if (lower.includes('watermark')) response = "Real academic certificates use secure watermarks embedded during paper manufacturing. We analyze pixels for fake digital watermarks!";
         if (lower.includes('blockchain') || lower.includes('hash')) response = "Every scan generates a Cryptographic SHA-256 hash. This simulates blockchain immutability so no one can alter the verification record.";
         if (lower.includes('tampering') || lower.includes('fake')) response = "Our system checks for font mismatches, unusual compression artifacts, and cross-references DB records to catch fake documents.";
         
         addChatMessage(response, 'bot');
    }, 600);
}

function addChatMessage(text, sender) {
    const history = document.getElementById('chat-history');
    if(!history) return;
    const div = document.createElement('div');
    div.className = `chat-message ${sender}`;
    div.innerText = text;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}
