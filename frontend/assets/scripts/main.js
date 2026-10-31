



// Javascript Logic

// Project Data for Modal
const projectsData = {
     1: {
          title: "DevFlow Analytics Engine",
          badge: "Flask + PostgreSQL",
          image: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=800",
          description: "DevFlow is a real-time team developer efficiency engine. It ingests commits, dynamic webhooks, and query logs to construct actionable charts for team leaders.",
          features: [
          "Asynchronous Flask background task processing",
          "PostgreSQL query optimization with custom indexes",
          "Interactive client-side Chart metrics using HTML Canvas",
          "Secure OAuth2 authentication for GitHub organizations"
          ],
          github: "https://github.com",
          live: "https://example.com"
     },
     2: {
          title: "EduPortal Instructor Hub",
          badge: "Python + MySQL",
          image: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&q=80&w=800",
          description: "EduPortal serves high-capacity software engineering bootcamps with auto-grading scripts, syllabus management, and real-time student submission tracking.",
          features: [
          "Automated Python test-runner isolation sandbox",
          "MySQL transactional schema for assignments & grading",
          "Role-based access control (Instructors, TAs, Students)",
          "Custom CSV/PDF grade report generator"
          ],
          github: "https://github.com",
          live: "https://example.com"
     },
     3: {
          title: "QueryPulse SQL Benchmarking",
          badge: "JavaScript + Tailwind",
          image: "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&q=80&w=800",
          description: "QueryPulse is an interactive visual benchmark utility helping backend engineers inspect execution trees and detect missing indexes across relational databases.",
          features: [
          "Visual query execution tree parser",
          "Side-by-side MySQL vs. PostgreSQL performance compare",
          "Instant JSON schema export & import",
          "Fully responsive mobile & desktop UI"
          ],
          github: "https://github.com",
          live: "https://example.com"
     }
};

// Dark / Light Theme Toggle Logic
const themeToggleBtn = document.getElementById('theme-toggle');
const darkIcon = document.getElementById('theme-toggle-dark-icon');
const lightIcon = document.getElementById('theme-toggle-light-icon');

function setTheme(theme) {
     const isDark = theme === 'dark';
     document.documentElement.classList.toggle('dark', isDark);
     darkIcon.classList.toggle('hidden', isDark);
     lightIcon.classList.toggle('hidden', !isDark);
     themeToggleBtn.setAttribute('aria-pressed', String(isDark));
}

// Check system preference or localStorage
const savedTheme = localStorage.getItem('color-theme');
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const initialTheme = savedTheme === 'dark' || savedTheme === 'light'
     ? savedTheme
     : (prefersDark ? 'dark' : 'light');
setTheme(initialTheme);

themeToggleBtn.addEventListener('click', function() {
     const nextTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
     setTheme(nextTheme);
     localStorage.setItem('color-theme', nextTheme);
});

// Mobile Drawer Toggle
const mobileBtn = document.getElementById('mobile-menu-btn');
const mobileMenu = document.getElementById('mobile-menu');
const mobileNavLinks = document.querySelectorAll('.mobile-nav-link');

mobileBtn.addEventListener('click', () => {
     mobileMenu.classList.toggle('hidden');
});

mobileNavLinks.forEach(link => {
     link.addEventListener('click', () => {
          mobileMenu.classList.add('hidden');
     });
});

// Experience Timeline Expand / Collapse
const experienceToggle = document.getElementById('experience-toggle');
const experienceToggleLabel = document.getElementById('experience-toggle-label');
const experienceToggleIcon = document.getElementById('experience-toggle-icon');
const extraExperienceItems = document.querySelectorAll('[data-experience-extra]');
const experienceList = document.getElementById('experience-list');
const experienceTimelineLine = document.getElementById('experience-timeline-line');

function updateExperienceTimelineLine() {
     const visibleMarkers = [...experienceList.querySelectorAll('[data-experience-marker]')]
          .filter(marker => !marker.closest('[data-experience-extra]')?.hidden);
     const lastMarker = visibleMarkers[visibleMarkers.length - 1];

     if (lastMarker) {
          const listTop = experienceList.getBoundingClientRect().top;
          const marker = lastMarker.getBoundingClientRect();
          experienceTimelineLine.style.height = `${marker.top + marker.height / 2 - listTop}px`;
     }
}

updateExperienceTimelineLine();
window.addEventListener('resize', updateExperienceTimelineLine);

experienceToggle.addEventListener('click', () => {
     const shouldExpand = experienceToggle.getAttribute('aria-expanded') !== 'true';

     extraExperienceItems.forEach(item => {
          item.hidden = !shouldExpand;
          item.classList.toggle('hidden', !shouldExpand);
          item.style.display = shouldExpand ? 'flex' : 'none';
     });

     updateExperienceTimelineLine();
     experienceToggle.setAttribute('aria-expanded', String(shouldExpand));
     experienceToggleLabel.textContent = shouldExpand ? 'Show less' : 'View all experience';
     experienceToggleIcon.classList.toggle('rotate-180', shouldExpand);
});

// Skill Filters Logic
const filterBtns = document.querySelectorAll('.filter-btn');
const skillCards = document.querySelectorAll('.skill-card');

filterBtns.forEach(btn => {
     btn.addEventListener('click', () => {
          // Update active state style
          filterBtns.forEach(b => {
          b.classList.remove('bg-gradient-to-r', 'from-pink-600', 'to-rose-600', 'text-white', 'shadow-md');
          b.classList.add('bg-slate-900', 'text-slate-300');
          });
          btn.classList.remove('bg-slate-900', 'text-slate-300');
          btn.classList.add('bg-gradient-to-r', 'from-pink-600', 'to-rose-600', 'text-white', 'shadow-md');

          const filter = btn.getAttribute('data-filter');

          skillCards.forEach(card => {
          if (filter === 'all' || card.getAttribute('data-category') === filter) {
               card.style.display = 'block';
          } else {
               card.style.display = 'none';
          }
          });
     });
});

// Project Modal Logic
const modal = document.getElementById('project-modal');
const modalBox = document.getElementById('modal-content-box');

function openProjectModal(id) {
     const data = projectsData[id];
     if (!data) return;

     document.getElementById('modal-title').innerText = data.title;
     document.getElementById('modal-badge').innerText = data.badge;
     document.getElementById('modal-image').src = data.image;
     document.getElementById('modal-description').innerText = data.description;
     document.getElementById('modal-github').href = data.github;
     document.getElementById('modal-live').href = data.live;

     const featuresList = document.getElementById('modal-features');
     featuresList.innerHTML = '';
     data.features.forEach(feat => {
          const li = document.createElement('li');
          li.innerText = feat;
          featuresList.appendChild(li);
     });

     modal.classList.remove('opacity-0', 'pointer-events-none');
     modalBox.classList.remove('scale-95');
     modalBox.classList.add('scale-100');
     document.body.style.overflow = 'hidden';
}

function closeProjectModal() {
     modal.classList.add('opacity-0', 'pointer-events-none');
     modalBox.classList.remove('scale-100');
     modalBox.classList.add('scale-95');
     document.body.style.overflow = 'auto';
}

modal.addEventListener('click', (e) => {
     if (e.target === modal) {
          closeProjectModal();
     }
});

document.querySelectorAll('[data-project-id]').forEach(card => {
     card.addEventListener('click', event => {
          if (event.target.closest('a')) return;
          openProjectModal(card.dataset.projectId);
     });
});

document.getElementById('modal-close').addEventListener('click', closeProjectModal);

// Contact Form Simulation & Toast Notifications
function showToast(message, type = 'success') {
     const container = document.getElementById('toast-container');
     const toast = document.createElement('div');
     
     const isSuccess = type === 'success';
     toast.className = `pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-2xl shadow-xl text-sm font-semibold transition-all transform translate-y-4 opacity-0 ${
          isSuccess 
          ? 'bg-gradient-to-r from-pink-600 to-rose-600 text-white' 
          : 'bg-red-600 text-white'
     }`;

     toast.innerHTML = `
          <i class="${isSuccess ? 'fa-solid fa-circle-check' : 'fa-solid fa-triangle-exclamation'} text-lg"></i>
          <span>${message}</span>
     `;

     container.appendChild(toast);

     // Animate In
     requestAnimationFrame(() => {
          toast.classList.remove('translate-y-4', 'opacity-0');
     });

     // Remove Toast after 4 seconds
     setTimeout(() => {
          toast.classList.add('translate-y-4', 'opacity-0');
          setTimeout(() => toast.remove(), 300);
     }, 4000);
}

async function handleContactSubmit(event) {
     event.preventDefault();
     const form = event.currentTarget;
     const submitBtn = document.getElementById('submit-btn');
     const originalButtonContent = submitBtn.innerHTML;
     submitBtn.disabled = true;
     submitBtn.classList.add('opacity-80');
     submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch animate-spin"></i> Sending...`;

     try {
          const formData = new FormData(form);
          const response = await fetch('/api/contact', {
               method: 'POST',
               headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
               },
               body: JSON.stringify(Object.fromEntries(formData.entries()))
          });
          const result = await response.json();

          if (!response.ok && response.status !== 202) {
               throw new Error(result.error || 'Unable to send your message. Please try again.');
          }

          showToast(result.message, response.status === 202 ? 'error' : 'success');
          form.reset();
     } catch (error) {
          showToast(error.message || 'Unable to reach the contact service. Please try again.', 'error');
     } finally {
          submitBtn.disabled = false;
          submitBtn.classList.remove('opacity-80');
          submitBtn.innerHTML = originalButtonContent;
     }
}

document.getElementById('contact-form').addEventListener('submit', handleContactSubmit);
