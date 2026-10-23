const registerForm = document.querySelector("#register-form");
const loginForm = document.querySelector("#login-form");
const registerPanel = document.querySelector("#register-panel");
const loginPanel = document.querySelector("#login-panel");
const paymentPanel = document.querySelector("#payment-panel");
const documentInput = document.querySelector("#document");
const documentLabel = document.querySelector("#document-label");
const documentHint = document.querySelector("#document-hint");
const loginIdentifier = document.querySelector("#login-identifier");
const loginIdentifierLabel = document.querySelector("#login-identifier-label");
const loginIdentifierHint = document.querySelector("#login-identifier-hint");
const sessionBar = document.querySelector("#session-bar");
const sessionChip = document.querySelector("#session-chip");
const sessionSummary = document.querySelector("#session-summary");
const walletRefreshButton = document.querySelector("#load-wallet");
const walletStatus = document.querySelector("#wallet-status");
const paymentForm = document.querySelector("#payment-form");
const paymentAmount = document.querySelector("#payment-amount");
const paymentAttemptCard = document.querySelector("#payment-attempt");
const attemptTitle = document.querySelector("#attempt-title");
const attemptDetail = document.querySelector("#attempt-detail");
const attemptStatus = document.querySelector("#attempt-status");
const paymentHistory = document.querySelector("#payment-history");
const paymentReceipt = document.querySelector("#payment-receipt");
const retryPaymentButton = document.querySelector("#retry-payment");
const resolvePaymentButton = document.querySelector("#resolve-payment");

const paymentStorageKey = "wallet-demo-payment-attempt";
const roleNames = { person: "Cliente", merchant: "Comercio" };
const paymentStates = ["PENDING", "SUCCEEDED", "REJECTED", "REVERSED"];
const errorLabels = {
  INSUFFICIENT_FUNDS: "Saldo insuficiente para este pago.",
  WALLET_NOT_ACTIVE: "La wallet no está activa.",
  IDEMPOTENCY_CONFLICT: "Esa clave de reintento ya se usó con otro contenido.",
  PAYMENT_NOT_ALLOWED: "Esta cuenta no puede realizar pagos.",
  PROVIDER_ERROR: "El proveedor simulado no está disponible.",
  TIMEOUT_AFTER_PROCESSING: "El proveedor procesó el pago pero la respuesta se perdió.",
};

const modal = Swal.mixin({
  customClass: { popup: "wallet-swal" },
  confirmButtonText: "Entendido",
  heightAuto: false,
});
const toast = Swal.mixin({
  toast: true,
  position: "top",
  showConfirmButton: false,
  timer: 3500,
  timerProgressBar: true,
  customClass: { popup: "wallet-toast" },
  heightAuto: false,
});

let currentWallet = null;
let currentUser = null;
let sessionTimer = null;
let sending = false;
let activePaymentAttempt = readPaymentAttempt();

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function summaryHtml(rows) {
  const items = rows
    .map(([label, value, isAmount]) => `<li><span>${escapeHtml(label)}</span><strong${isAmount ? ' class="is-amount"' : ""}>${escapeHtml(value)}</strong></li>`)
    .join("");
  return `<ul class="swal-summary">${items}</ul>`;
}

function selectedRole(groupName) {
  return document.querySelector(`input[name="${groupName}"]:checked`).value;
}

function updateRoleLabels() {
  const role = selectedRole("role");
  const loginRole = selectedRole("login-role");
  const documentType = role === "person" ? "DNI" : "RUC";
  const digits = role === "person" ? 8 : 11;
  const loginDocumentType = loginRole === "person" ? "DNI" : "RUC";
  const loginDigits = loginRole === "person" ? 8 : 11;

  documentLabel.textContent = `${documentType} ficticio`;
  documentInput.placeholder = `TEST-${"0".repeat(digits)}`;
  documentHint.textContent =
    role === "person"
      ? "TEST- seguido de 8 dígitos. No uses un documento real."
      : "TEST- seguido de 11 dígitos con control válido. No uses un RUC real.";

  loginIdentifierLabel.textContent = `${loginDocumentType} ficticio o correo`;
  loginIdentifier.placeholder = `TEST-${"0".repeat(loginDigits)} o demo@example.test`;
  loginIdentifierHint.textContent = `Usa el código TEST de ${loginDigits} dígitos o el correo de tu cuenta.`;
}

function setFieldError(fieldName, message) {
  const input = document.querySelector(`[name="${fieldName}"]`);
  const error = document.querySelector(`#${fieldName}-error`);
  if (!input || !error) return;

  input.setAttribute("aria-invalid", message ? "true" : "false");
  error.textContent = message;
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function normalizeTestDocument(value, role) {
  const documentCode = value.trim().toUpperCase();
  const digitCount = role === "person" ? 8 : 11;
  const match = documentCode.match(new RegExp(`^TEST-(\\d{${digitCount}})$`));

  if (!match) return null;
  if (role === "merchant" && !hasValidRucCheckDigit(match[1])) return null;
  return documentCode;
}

function hasValidRucCheckDigit(digits) {
  const weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
  const weightedSum = weights.reduce(
    (sum, weight, index) => sum + Number(digits[index]) * weight,
    0,
  );
  let checkDigit = 11 - (weightedSum % 11);
  if (checkDigit === 10) checkDigit = 0;
  if (checkDigit === 11) checkDigit = 1;
  return Number(digits[10]) === checkDigit;
}

function isValidPeruvianMobile(value) {
  const compact = value.trim().replace(/[\s-]/g, "");
  const nationalNumber = compact.startsWith("+51") ? compact.slice(3) : compact;
  return /^9\d{8}$/.test(nationalNumber);
}

function formatPen(cents) {
  return new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: "PEN",
  }).format(cents / 100);
}

function tagSeverity(status) {
  if (status === "ACTIVE" || status === "SUCCEEDED") return "success";
  if (status === "PENDING") return "warning";
  if (status === "REJECTED") return "danger";
  if (status === "REVERSED") return "info";
  return "secondary";
}

function setTag(element, status, label = status) {
  element.className = `p-tag p-component p-tag-${tagSeverity(status)}`;
  element.textContent = label;
}

function recipientLabel(recipient) {
  return recipient === "merchant-demo" ? "Comercio de prueba" : "Persona de prueba";
}

function recipientIcon(recipient) {
  return recipient === "merchant-demo" ? "storefront" : "person";
}

function canPay() {
  return currentUser?.role === "person" && currentUser.status === "ACTIVE";
}

function formatCountdown(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function resetWalletView() {
  currentWallet = null;
  document.querySelector("#wallet-available").textContent = "S/ —";
  document.querySelector("#wallet-balance").textContent = "—";
  document.querySelector("#wallet-reserved").textContent = "—";
  setTag(walletStatus, "", "—");
}

function setSession(account) {
  clearInterval(sessionTimer);
  currentUser = account;
  sessionBar.hidden = !account;
  if (!account) {
    resetWalletView();
    paymentReceipt.hidden = true;
    paymentHistory.replaceChildren();
    return;
  }

  let remaining = account.sessionSecondsLeft;
  sessionChip.title = account.document;
  const render = () => {
    sessionSummary.textContent = `${roleNames[account.role]} · ${formatCountdown(remaining)}`;
    sessionChip.classList.toggle("is-low", remaining <= 60);
  };
  render();
  sessionTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      expireSession();
      return;
    }
    render();
  }, 1000);
}

function expireSession() {
  if (!currentUser) return;
  setSession(null);
  switchMode("login");
  void modal.fire({
    icon: "warning",
    title: "Tu sesión venció",
    text: "Por seguridad la sesión dura 5 minutos. Ingresa de nuevo para continuar.",
  });
}

function isUnauthenticated(response) {
  if (response.status !== 401) return false;
  expireSession();
  return true;
}

function accountStatusMessage(account) {
  if (account.role !== "person") {
    return "Las cuentas de comercio reciben pagos; solo los clientes pueden pagar.";
  }
  return `Tu billetera está bloqueada (estado ${account.status}). Puedes consultar tu estado, pero no pagar.`;
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { response, result: await readJsonResponse(response) };
}

function authErrorMessage(status, code, fallback) {
  if (status === 409) return "No se pudo completar el registro con esos datos. Revisa la información o ingresa si ya tienes cuenta.";
  if (status === 429) return "Demasiados intentos. Espera 5 minutos antes de volver a intentar.";
  if (status === 401) return "Credenciales inválidas.";
  if (code === "KYC_UNAVAILABLE") return "El servicio de verificación no está disponible. No se creó la cuenta; inténtalo más tarde.";
  if (status === 400) return "Revisa los datos del formulario.";
  return fallback;
}

async function loadDemoWallet() {
  walletRefreshButton.disabled = true;
  try {
    const response = await fetch("/api/wallets/wallet-demo", {
      headers: { Accept: "application/json" },
    });
    if (isUnauthenticated(response)) return;
    const wallet = await readJsonResponse(response);

    if (!response.ok) {
      throw new Error(wallet.error || "WALLET_UNAVAILABLE");
    }
    if (
      wallet.id !== "wallet-demo" ||
      wallet.currency !== "PEN" ||
      ![wallet.balance, wallet.reserved, wallet.available].every(Number.isInteger) ||
      wallet.available !== wallet.balance - wallet.reserved
    ) {
      throw new Error("INVALID_WALLET_RESPONSE");
    }

    document.querySelector("#wallet-id").textContent = wallet.id;
    setTag(walletStatus, wallet.status);
    document.querySelector("#wallet-available").textContent = formatPen(wallet.available);
    document.querySelector("#wallet-balance").textContent = formatPen(wallet.balance);
    document.querySelector("#wallet-reserved").textContent = formatPen(wallet.reserved);
    currentWallet = wallet;
  } catch {
    currentWallet = null;
    void toast.fire({ icon: "error", title: "No se pudo consultar el saldo" });
  } finally {
    walletRefreshButton.disabled = false;
  }
}

function readPaymentAttempt() {
  try {
    const attempt = JSON.parse(sessionStorage.getItem(paymentStorageKey));
    if (
      attempt &&
      typeof attempt.idempotencyKey === "string" &&
      attempt.payload?.walletId === "wallet-demo" &&
      ["contact-demo", "merchant-demo"].includes(attempt.payload.recipient) &&
      Number.isInteger(attempt.payload.amountCents)
    ) {
      return attempt;
    }
  } catch {
    try {
      sessionStorage.removeItem(paymentStorageKey);
    } catch {
      return null;
    }
  }
  return null;
}

function savePaymentAttempt() {
  if (!activePaymentAttempt) return false;
  try {
    sessionStorage.setItem(paymentStorageKey, JSON.stringify(activePaymentAttempt));
    return true;
  } catch {
    void modal.fire({
      icon: "error",
      title: "No se pudo proteger el reintento",
      text: "El navegador no permitió guardar la clave del pago en esta pestaña, así que no se envió.",
    });
    return false;
  }
}

function clearPaymentAttempt() {
  activePaymentAttempt = null;
  sessionStorage.removeItem(paymentStorageKey);
  renderAttempt();
}

function renderAttempt() {
  const attempt = activePaymentAttempt;
  paymentAttemptCard.hidden = !attempt;
  paymentForm.hidden = Boolean(attempt);
  updatePaymentFormState();
  if (!attempt) return;

  const amount = formatPen(attempt.payload.amountCents);
  const hasId = Boolean(attempt.paymentId);
  if (sending) {
    attemptTitle.textContent = "Enviando al proveedor simulado…";
    attemptDetail.textContent = `${amount} a ${recipientLabel(attempt.payload.recipient)}`;
    setTag(attemptStatus, "PENDING", "Enviando");
  } else if (hasId) {
    attemptTitle.textContent = "Pago pendiente de confirmación";
    attemptDetail.textContent = `Referencia ${attempt.paymentId} · ${amount}`;
    setTag(attemptStatus, "PENDING", "Pendiente");
  } else {
    attemptTitle.textContent = "Resultado incierto";
    attemptDetail.textContent = `${amount} a ${recipientLabel(attempt.payload.recipient)}. Reintenta con la misma clave; no se creará otro cobro.`;
    setTag(attemptStatus, "REJECTED", "Sin respuesta");
  }
  resolvePaymentButton.hidden = sending || !hasId;
  retryPaymentButton.hidden = sending || hasId;
}

function updatePaymentFormState() {
  const blocked = !canPay();
  paymentForm.querySelectorAll("input, button").forEach((control) => {
    control.disabled = blocked;
  });
}

function amountToCents(value) {
  const normalized = value.trim().replace(",", ".");
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [soles, cents = ""] = normalized.split(".");
  const amount = Number(soles) * 100 + Number(cents.padEnd(2, "0"));
  return Number.isSafeInteger(amount) && amount > 0 && amount <= 100_000_000
    ? amount
    : null;
}

async function showPaymentState(payment) {
  activePaymentAttempt = {
    ...activePaymentAttempt,
    paymentId: payment.id,
    status: payment.status,
  };
  savePaymentAttempt();

  if (payment.status === "PENDING") {
    renderAttempt();
    void loadDemoWallet();
    await modal.fire({
      icon: "info",
      title: "Pago pendiente",
      html: summaryHtml([
        ["Referencia", payment.id],
        ["Monto", formatPen(payment.amountCents), true],
      ]) + "<p>El importe queda reservado hasta confirmar el resultado. Pulsa «Consultar resultado».</p>",
    });
    return;
  }

  clearPaymentAttempt();
  paymentForm.reset();
  void loadDemoWallet();
  void loadPaymentHistory();

  if (payment.status === "SUCCEEDED" || payment.status === "REVERSED") {
    void loadReceipt(payment.id);
    await modal.fire({
      icon: payment.status === "SUCCEEDED" ? "success" : "info",
      title: payment.status === "SUCCEEDED" ? "¡Pago confirmado!" : "Pago reversado",
      html: summaryHtml([
        ["Referencia", payment.id],
        ["Destinatario", recipientLabel(payment.recipient)],
        ["Monto", formatPen(payment.amountCents), true],
      ]),
    });
    return;
  }
  await modal.fire({
    icon: "error",
    title: "Pago rechazado",
    text: `El proveedor confirmó ${payment.status}. No se realizó ningún cobro.`,
  });
}

async function handlePaymentError(response, result) {
  const code = typeof result?.error === "string" ? result.error : "PAYMENT_REQUEST_FAILED";
  const detail = errorLabels[code] ?? "Inténtalo nuevamente.";

  if ([502, 503, 504].includes(response.status)) {
    if (result?.paymentId) {
      activePaymentAttempt.paymentId = result.paymentId;
      savePaymentAttempt();
      renderAttempt();
      await modal.fire({
        icon: "warning",
        title: "Resultado incierto",
        text: `${detail} Conservamos el intento ${result.paymentId}: consulta el resultado, no crees otro pago.`,
      });
    } else {
      renderAttempt();
      await modal.fire({
        icon: "warning",
        title: "Sin respuesta definitiva",
        text: `${detail} Puedes reintentar el mismo intento con su clave original (${code}).`,
      });
    }
    return;
  }

  clearPaymentAttempt();
  if (code === "INSUFFICIENT_FUNDS" || code === "WALLET_NOT_ACTIVE") {
    void loadDemoWallet();
  }
  await modal.fire({
    icon: "error",
    title: "El pago no se realizó",
    text: `${detail} (${code}). No se mostrará como exitoso.`,
  });
}

async function sendPaymentAttempt() {
  if (!activePaymentAttempt || sending) return;
  sending = true;
  renderAttempt();

  try {
    const response = await fetch("/api/payments", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": activePaymentAttempt.idempotencyKey,
      },
      body: JSON.stringify(activePaymentAttempt.payload),
    });
    if (isUnauthenticated(response)) return;
    const result = await readJsonResponse(response);
    if (!response.ok) {
      sending = false;
      await handlePaymentError(response, result);
      return;
    }
    if (!result.id || !paymentStates.includes(result.status)) {
      sending = false;
      renderAttempt();
      await modal.fire({
        icon: "warning",
        title: "Respuesta no válida",
        text: "No recibimos un resultado de pago reconocible. Conservamos la misma clave para consultar o reintentar.",
      });
      return;
    }
    sending = false;
    await showPaymentState(result);
  } catch {
    sending = false;
    renderAttempt();
    await modal.fire({
      icon: "warning",
      title: "No se pudo confirmar la respuesta",
      text: "Conservamos la clave y el mismo contenido para un reintento seguro.",
    });
  } finally {
    sending = false;
    renderAttempt();
  }
}

async function resolveActivePayment() {
  if (!activePaymentAttempt?.paymentId) return;
  resolvePaymentButton.disabled = true;

  try {
    const response = await fetch(
      `/api/payments/${encodeURIComponent(activePaymentAttempt.paymentId)}/resolve`,
      { method: "POST", headers: { Accept: "application/json" } },
    );
    if (isUnauthenticated(response)) return;
    const result = await readJsonResponse(response);
    if (response.status === 202 && result.status === "PENDING") {
      void loadPaymentHistory();
      await modal.fire({
        icon: "info",
        title: "Sigue pendiente",
        text: "Se abrió o actualizó el caso de soporte del mock. Vuelve a consultar más tarde.",
      });
      return;
    }
    if (!response.ok) {
      await handlePaymentError(response, result);
      return;
    }
    if (!result.id || !paymentStates.includes(result.status)) {
      await modal.fire({
        icon: "warning",
        title: "Estado no reconocido",
        text: "El servicio no devolvió un estado de pago reconocido.",
      });
      return;
    }
    await showPaymentState(result);
  } catch {
    void toast.fire({ icon: "error", title: "No se pudo consultar el resultado" });
  } finally {
    resolvePaymentButton.disabled = false;
  }
}

async function loadReceipt(paymentId) {
  try {
    const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/receipt`, {
      headers: { Accept: "application/json" },
    });
    if (isUnauthenticated(response)) return;
    const receipt = await readJsonResponse(response);
    if (!response.ok) return;

    document.querySelector("#receipt-id").textContent = receipt.paymentId;
    document.querySelector("#receipt-recipient").textContent = recipientLabel(receipt.recipient);
    document.querySelector("#receipt-amount").textContent = formatPen(receipt.amountCents);
    document.querySelector("#receipt-status").textContent = receipt.status;
    paymentReceipt.hidden = false;
  } catch {
    paymentReceipt.hidden = true;
  }
}

function historyMessage(icon, text) {
  const message = document.createElement("p");
  message.className = "history-empty";
  const glyph = document.createElement("span");
  glyph.className = "material-icons";
  glyph.setAttribute("aria-hidden", "true");
  glyph.textContent = icon;
  message.append(glyph, text);
  return message;
}

async function loadPaymentHistory() {
  paymentHistory.replaceChildren(historyMessage("hourglass_empty", "Consultando historial…"));

  try {
    const response = await fetch("/api/payments?walletId=wallet-demo", {
      headers: { Accept: "application/json" },
    });
    if (isUnauthenticated(response)) return;
    const history = await readJsonResponse(response);
    if (!response.ok || !Array.isArray(history)) {
      throw new Error("PAYMENT_HISTORY_UNAVAILABLE");
    }
    if (history.length === 0) {
      paymentHistory.replaceChildren(historyMessage("inbox", "Aún no hay pagos en wallet-demo."));
      return;
    }

    const items = history.map((payment) => {
      const item = document.createElement("article");
      item.className = "history-item";

      const avatar = document.createElement("span");
      avatar.className = "history-avatar";
      const icon = document.createElement("span");
      icon.className = "material-icons";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = recipientIcon(payment.recipient);
      avatar.append(icon);

      const name = document.createElement("strong");
      name.className = "history-name";
      name.textContent = recipientLabel(payment.recipient);
      const amount = document.createElement("span");
      amount.className = "history-amount";
      amount.textContent = formatPen(payment.amountCents);
      const reference = document.createElement("span");
      reference.className = "history-ref";
      reference.textContent = `Ref. ${payment.id}`;
      const status = document.createElement("span");
      setTag(status, payment.status);

      item.append(avatar, name, amount, reference, status);
      return item;
    });
    paymentHistory.replaceChildren(...items);
  } catch {
    paymentHistory.replaceChildren(historyMessage("error_outline", "No se pudo consultar el historial."));
  }
}

function switchMode(mode) {
  if (mode === "payment" && !currentUser) {
    mode = "login";
    void toast.fire({ icon: "info", title: "Ingresa con tu cuenta para pagar" });
  }
  registerPanel.hidden = mode !== "register";
  loginPanel.hidden = mode !== "login";
  paymentPanel.hidden = mode !== "payment";

  document.querySelectorAll(".mode-tab").forEach((tab) => {
    const selected = tab.dataset.mode === mode;
    tab.parentElement.classList.toggle("p-highlight", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });

  if (mode === "payment") {
    renderAttempt();
    if (!canPay()) {
      void toast.fire({ icon: "warning", title: accountStatusMessage(currentUser), timer: 6000 });
    } else if (activePaymentAttempt && !sending) {
      void toast.fire({ icon: "info", title: "Tienes un intento guardado; resuélvelo antes de pagar de nuevo", timer: 5000 });
    }
    void loadDemoWallet();
    void loadPaymentHistory();
  }
}

document.querySelectorAll(".mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => switchMode(tab.dataset.mode));
});

document.querySelectorAll('input[name="role"], input[name="login-role"]').forEach((radio) => {
  radio.addEventListener("change", updateRoleLabels);
});

document.addEventListener("input", (event) => {
  if (event.target?.name) setFieldError(event.target.name, "");
});

document.querySelectorAll(".toggle-visibility").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.target);
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    button.querySelector(".material-icons").textContent = reveal ? "visibility_off" : "visibility";
    button.setAttribute("aria-label", reveal ? "Ocultar contraseña" : "Mostrar contraseña");
  });
});

document.querySelectorAll("[data-amount]").forEach((button) => {
  button.addEventListener("click", () => {
    paymentAmount.value = button.dataset.amount;
    setFieldError("payment-amount", "");
    paymentAmount.focus();
  });
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const role = selectedRole("role");
  const email = document.querySelector("#email").value.trim();
  const phone = document.querySelector("#phone").value.trim();
  const password = document.querySelector("#password").value;
  const documentCode = normalizeTestDocument(documentInput.value, role);
  const errors = {
    document: documentCode ? "" : `Ingresa un código ficticio TEST con ${role === "person" ? "8 dígitos" : "11 dígitos y control válido"}.`,
    email: isValidEmail(email) ? "" : "Ingresa un correo de prueba con formato válido.",
    phone: isValidPeruvianMobile(phone) ? "" : "Ingresa 9 dígitos ficticios que empiecen en 9; puedes incluir +51, espacios o guiones.",
    password: password.length >= 8 && password.length <= 128 ? "" : "Usa entre 8 y 128 caracteres.",
  };

  Object.entries(errors).forEach(([field, message]) => setFieldError(field, message));

  if (Object.values(errors).some(Boolean)) {
    void toast.fire({ icon: "warning", title: "Revisa los campos marcados" });
    return;
  }

  const submitButton = registerForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  try {
    const { response, result } = await postJson("/api/auth/register", {
      role,
      document: documentCode,
      email,
      phone,
      password,
    });
    if (!response.ok) {
      await modal.fire({
        icon: "error",
        title: "No se pudo crear la cuenta",
        text: authErrorMessage(response.status, result.error, "Inténtalo de nuevo."),
      });
      return;
    }
    registerForm.reset();
    updateRoleLabels();
    const active = result.status === "ACTIVE";
    await modal.fire({
      icon: active ? "success" : "info",
      title: "Cuenta creada",
      text: active
        ? "Tu billetera está activa. Ya puedes ingresar."
        : `Estado de la billetera: ${result.status}. Podrás ingresar para consultarlo, pero estará bloqueada.`,
      confirmButtonText: "Ir a ingresar",
    });
    switchMode("login");
  } catch {
    await modal.fire({
      icon: "error",
      title: "Sin conexión con el servidor",
      text: "Verifica que esté iniciado e inténtalo otra vez.",
    });
  } finally {
    submitButton.disabled = false;
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const role = selectedRole("login-role");
  const identifier = loginIdentifier.value.trim();
  const password = document.querySelector("#login-password").value;
  const isEmail = identifier.includes("@");
  const validIdentifier = isEmail
    ? isValidEmail(identifier)
    : Boolean(normalizeTestDocument(identifier, role));
  const errors = {
    "login-identifier": validIdentifier
      ? ""
      : isEmail
        ? "Ingresa un correo de prueba con formato válido."
        : `Ingresa un código ficticio TEST válido para ${role === "person" ? "DNI" : "RUC"}.`,
    "login-password": password.length > 0 ? "" : "Ingresa tu contraseña.",
  };

  Object.entries(errors).forEach(([field, message]) => setFieldError(field, message));

  if (Object.values(errors).some(Boolean)) {
    void toast.fire({ icon: "warning", title: "Revisa los campos marcados" });
    return;
  }

  const submitButton = loginForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  try {
    const { response, result } = await postJson("/api/auth/login", { role, identifier, password });
    if (!response.ok) {
      await modal.fire({
        icon: "error",
        title: "No se pudo ingresar",
        text: authErrorMessage(response.status, result.error, "Inténtalo de nuevo."),
      });
      return;
    }
    loginForm.reset();
    updateRoleLabels();
    setSession(result);
    if (canPay()) {
      void toast.fire({ icon: "success", title: "¡Bienvenido!" });
      switchMode("payment");
    } else {
      await modal.fire({ icon: "info", title: "Cuenta con restricciones", text: accountStatusMessage(result) });
    }
  } catch {
    await modal.fire({
      icon: "error",
      title: "Sin conexión con el servidor",
      text: "Verifica que esté iniciado e inténtalo otra vez.",
    });
  } finally {
    submitButton.disabled = false;
  }
});

paymentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  paymentReceipt.hidden = true;

  if (activePaymentAttempt) {
    void toast.fire({ icon: "warning", title: "Resuelve el intento actual antes de iniciar otro pago" });
    return;
  }
  if (!currentWallet) {
    setFieldError("payment-amount", "Primero actualiza el saldo para validar el disponible.");
    return;
  }
  const amountCents = amountToCents(paymentAmount.value);
  if (amountCents === null) {
    setFieldError("payment-amount", "Ingresa un monto positivo en soles con máximo dos decimales.");
    return;
  }
  if (currentWallet.status !== "ACTIVE") {
    setFieldError("payment-amount", "La wallet no está activa y no puede realizar pagos.");
    return;
  }
  if (amountCents > currentWallet.available) {
    setFieldError("payment-amount", `El monto supera el disponible (${formatPen(currentWallet.available)}).`);
    return;
  }
  setFieldError("payment-amount", "");

  const payload = {
    walletId: "wallet-demo",
    recipient: document.querySelector('input[name="recipient"]:checked').value,
    amountCents,
    currency: "PEN",
  };
  const { isConfirmed } = await modal.fire({
    icon: "question",
    title: "Confirma tu pago",
    html: summaryHtml([
      ["Destinatario", recipientLabel(payload.recipient)],
      ["Monto", formatPen(amountCents), true],
      ["Moneda", "PEN · Sol peruano"],
    ]),
    showCancelButton: true,
    reverseButtons: true,
    confirmButtonText: "Confirmar y enviar",
    cancelButtonText: "Editar",
  });
  if (!isConfirmed || activePaymentAttempt) return;

  activePaymentAttempt = { idempotencyKey: crypto.randomUUID(), payload };
  if (!savePaymentAttempt()) {
    activePaymentAttempt = null;
    renderAttempt();
    return;
  }
  void sendPaymentAttempt();
});

retryPaymentButton.addEventListener("click", () => {
  if (activePaymentAttempt && !activePaymentAttempt.paymentId) {
    void sendPaymentAttempt();
  }
});

resolvePaymentButton.addEventListener("click", () => {
  void resolveActivePayment();
});

walletRefreshButton.addEventListener("click", () => {
  void loadDemoWallet();
});

document.querySelector("#refresh-history").addEventListener("click", () => {
  void loadPaymentHistory();
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await postJson("/api/auth/logout", {});
  } catch {
    // La sesión local se limpia igual; la del servidor vence a los 300 s.
  }
  setSession(null);
  switchMode("login");
  void toast.fire({ icon: "success", title: "Cerraste sesión" });
});

async function restoreSession() {
  try {
    const response = await fetch("/api/auth/me", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    setSession(await response.json());
    if (canPay()) {
      switchMode("payment");
    }
  } catch {
    // Sin servidor no hay sesión que restaurar.
  }
}

updateRoleLabels();
switchMode("register");
renderAttempt();
void restoreSession();
