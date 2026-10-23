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
const downloadReceiptButton = document.querySelector("#download-receipt");
const retryPaymentButton = document.querySelector("#retry-payment");
const resolvePaymentButton = document.querySelector("#resolve-payment");
const recipientInput = document.querySelector("#recipient-number");
const recipientResult = document.querySelector("#recipient-result");
const recipientResultLabel = document.querySelector("#recipient-result-label");
const recipientResultIcon = document.querySelector("#recipient-result-icon");

const paymentStorageKey = "wallet-demo-payment-attempt";
const roleNames = { person: "Cliente", merchant: "Comercio" };
const roleIcons = { person: "person", merchant: "storefront" };
const paymentStates = ["PENDING", "SUCCEEDED", "REJECTED", "REVERSED"];
const errorLabels = {
  INSUFFICIENT_FUNDS: "Saldo insuficiente para este pago.",
  WALLET_NOT_ACTIVE: "La wallet no está activa.",
  IDEMPOTENCY_CONFLICT: "Esa clave de reintento ya se usó con otro contenido.",
  PAYMENT_NOT_ALLOWED: "Esta cuenta no puede realizar pagos.",
  PROVIDER_ERROR: "El proveedor simulado no está disponible.",
  TIMEOUT_AFTER_PROCESSING: "El proveedor procesó el pago pero la respuesta se perdió.",
  RECIPIENT_NOT_FOUND: "No hay una cuenta activa con ese número.",
  SELF_PAYMENT: "No puedes pagarte a ti mismo.",
  INVALID_RECIPIENT: "Ingresa un celular, DNI o RUC válido.",
  TOO_MANY_ATTEMPTS: "Demasiadas consultas de destinatario. Espera unos minutos.",
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
});

let currentWallet = null;
let currentUser = null;
let sessionTimer = null;
let sending = false;
let receiptPaymentId = null;
let resolvedRecipient = null;
let recipientTimer = null;
let recipientRequestId = 0;
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

  documentLabel.textContent = documentType;
  documentInput.placeholder = role === "person" ? "12345678" : "20123456786";
  documentInput.maxLength = digits;
  documentHint.textContent =
    role === "person"
      ? "8 dígitos. No uses un documento real."
      : "11 dígitos con dígito de control válido. No uses un RUC real.";

  loginIdentifierLabel.textContent = `${loginDocumentType} o correo`;
  loginIdentifier.placeholder = `${loginDigits === 8 ? "12345678" : "20123456786"} o demo@example.test`;
  loginIdentifierHint.textContent = `Tu ${loginDocumentType} de ${loginDigits} dígitos o el correo de tu cuenta.`;
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

function normalizeDocument(value, role) {
  const digitCount = role === "person" ? 8 : 11;
  const digits = value.trim().toUpperCase().replace(/^TEST-/, "");

  if (!new RegExp(`^\\d{${digitCount}}$`).test(digits)) return null;
  if (role === "merchant" && !hasValidRucCheckDigit(digits)) return null;
  return digits;
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

function paymentRecipientName(payment) {
  return payment.recipientLabel ?? recipientLabel(payment.recipient);
}

// Refleja classify_identifier del servidor; el servidor vuelve a validar y decide.
function parseRecipientNumber(value) {
  const compact = value.trim().toUpperCase().replace(/^TEST-/, "").replace(/[\s-]/g, "").replace(/^\+51/, "");
  if (/^9\d{8}$/.test(compact)) return `+51${compact}`;
  if (/^\d{8}$/.test(compact)) return compact;
  if (/^\d{11}$/.test(compact) && hasValidRucCheckDigit(compact)) return compact;
  return null;
}

function clearRecipient() {
  recipientRequestId += 1;
  clearTimeout(recipientTimer);
  resolvedRecipient = null;
  recipientResult.hidden = true;
}

function scheduleRecipientLookup() {
  clearRecipient();
  setFieldError("recipient", "");
  const value = recipientInput.value;
  if (!value.trim()) return;

  const normalized = parseRecipientNumber(value);
  if (normalized === null) {
    if (value.replace(/\D/g, "").length >= 8) {
      setFieldError("recipient", errorLabels.INVALID_RECIPIENT);
    }
    return;
  }
  const requestId = recipientRequestId;
  recipientTimer = setTimeout(() => lookupRecipient(normalized, requestId), 350);
}

async function lookupRecipient(normalized, requestId) {
  try {
    const { response, result } = await postJson("/api/recipients/resolve", { identifier: normalized });
    if (requestId !== recipientRequestId) return;
    if (isUnauthenticated(response)) return;
    if (!response.ok) {
      const code = typeof result?.error === "string" ? result.error : "";
      setFieldError("recipient", errorLabels[code] ?? "No se pudo buscar el destinatario.");
      return;
    }
    if (typeof result.label !== "string" || !roleIcons[result.role]) {
      setFieldError("recipient", "No se pudo buscar el destinatario.");
      return;
    }
    resolvedRecipient = { number: normalized, role: result.role, label: result.label };
    recipientResultLabel.textContent = result.label;
    recipientResultIcon.textContent = roleIcons[result.role];
    recipientResult.hidden = false;
  } catch {
    if (requestId === recipientRequestId) {
      setFieldError("recipient", "No se pudo buscar el destinatario.");
    }
  }
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
    paymentForm.reset();
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
      typeof attempt.payload.recipientNumber === "string" &&
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
  const who = attempt.recipientLabel ?? "el destinatario elegido";
  const hasId = Boolean(attempt.paymentId);
  if (sending) {
    attemptTitle.textContent = "Enviando al proveedor simulado…";
    attemptDetail.textContent = `${amount} a ${who}`;
    setTag(attemptStatus, "PENDING", "Enviando");
  } else if (hasId) {
    attemptTitle.textContent = "Pago pendiente de confirmación";
    attemptDetail.textContent = `Referencia ${attempt.paymentId} · ${amount}`;
    setTag(attemptStatus, "PENDING", "Pendiente");
  } else {
    attemptTitle.textContent = "Resultado incierto";
    attemptDetail.textContent = `${amount} a ${who}. Reintenta con la misma clave; no se creará otro cobro.`;
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
  const activePaymentLabel = activePaymentAttempt?.recipientLabel;
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
    const { dismiss } = await modal.fire({
      icon: payment.status === "SUCCEEDED" ? "success" : "info",
      title: payment.status === "SUCCEEDED" ? "¡Pago confirmado!" : "Pago reversado",
      html: summaryHtml([
        ["Referencia", payment.id],
        ["Destinatario", payment.recipientLabel ?? activePaymentLabel ?? recipientLabel(payment.recipient)],
        ["Monto", formatPen(payment.amountCents), true],
      ]),
      confirmButtonText: "Listo",
      showCancelButton: true,
      cancelButtonText: "Descargar PDF",
      reverseButtons: true,
    });
    if (dismiss === Swal.DismissReason.cancel) {
      await downloadReceiptPdf(payment.id);
    }
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

async function downloadReceiptPdf(paymentId, button) {
  if (button) button.disabled = true;
  try {
    const response = await fetch(`/api/payments/${encodeURIComponent(paymentId)}/receipt.pdf`, {
      headers: { Accept: "application/pdf" },
    });
    if (isUnauthenticated(response)) return;
    if (!response.ok) {
      const { error } = await readJsonResponse(response);
      await modal.fire({
        icon: "warning",
        title: "No se pudo descargar",
        text: error === "RECEIPT_NOT_READY"
          ? "El comprobante estará disponible cuando el pago esté confirmado."
          : "No se pudo generar el comprobante. Inténtalo de nuevo.",
      });
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `comprobante-${paymentId}.pdf`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    void toast.fire({ icon: "success", title: "Comprobante descargado" });
  } catch {
    void toast.fire({ icon: "error", title: "No se pudo descargar el comprobante" });
  } finally {
    if (button) button.disabled = false;
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

    receiptPaymentId = receipt.paymentId;
    document.querySelector("#receipt-id").textContent = receipt.paymentId;
    document.querySelector("#receipt-recipient").textContent = paymentRecipientName(receipt);
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
      name.textContent = paymentRecipientName(payment);
      const amount = document.createElement("span");
      amount.className = "history-amount";
      amount.textContent = formatPen(payment.amountCents);
      const reference = document.createElement("span");
      reference.className = "history-ref";
      reference.textContent = `Ref. ${payment.id}`;
      const status = document.createElement("span");
      setTag(status, payment.status);
      const actions = document.createElement("span");
      actions.className = "history-actions";
      actions.append(status);
      if (payment.status === "SUCCEEDED" || payment.status === "REVERSED") {
        const download = document.createElement("button");
        download.type = "button";
        download.className = "p-button p-component p-button-icon-only p-button-rounded p-button-text p-button-sm";
        download.title = "Descargar comprobante en PDF";
        download.setAttribute("aria-label", `Descargar comprobante en PDF del pago ${payment.id}`);
        const glyph = document.createElement("span");
        glyph.className = "material-icons p-button-icon";
        glyph.setAttribute("aria-hidden", "true");
        glyph.textContent = "picture_as_pdf";
        download.append(glyph);
        download.addEventListener("click", () => downloadReceiptPdf(payment.id, download));
        actions.append(download);
      }

      item.append(avatar, name, amount, reference, actions);
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
  if (event.target?.name && event.target !== recipientInput) setFieldError(event.target.name, "");
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
  const documentCode = normalizeDocument(documentInput.value, role);
  const errors = {
    document: documentCode ? "" : role === "person" ? "Ingresa un DNI de 8 dígitos." : "Ingresa un RUC de 11 dígitos con dígito de control válido.",
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
    setSession(result);
    if (canPay()) {
      void toast.fire({ icon: "success", title: "Cuenta creada. ¡Ya iniciaste sesión!" });
      switchMode("payment");
    } else {
      switchMode("login");
      await modal.fire({
        icon: "info",
        title: "Cuenta creada",
        text: `Iniciaste sesión. ${accountStatusMessage(result)}`,
      });
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

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const role = selectedRole("login-role");
  const identifier = loginIdentifier.value.trim();
  const password = document.querySelector("#login-password").value;
  const isEmail = identifier.includes("@");
  const validIdentifier = isEmail
    ? isValidEmail(identifier)
    : Boolean(normalizeDocument(identifier, role));
  const errors = {
    "login-identifier": validIdentifier
      ? ""
      : isEmail
        ? "Ingresa un correo con formato válido."
        : `Ingresa tu ${role === "person" ? "DNI de 8 dígitos" : "RUC de 11 dígitos"} o tu correo.`,
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

  const recipient = resolvedRecipient;
  if (!recipient) {
    setFieldError("recipient", recipientInput.value.trim() ? "Espera a que se encuentre la cuenta del destinatario." : "Ingresa el número del destinatario.");
    recipientInput.focus();
    return;
  }

  const payload = {
    walletId: "wallet-demo",
    recipientNumber: recipient.number,
    amountCents,
    currency: "PEN",
  };
  const { isConfirmed } = await modal.fire({
    icon: "question",
    title: "Confirma tu pago",
    html: summaryHtml([
      ["Destinatario", recipient.label],
      ["Monto", formatPen(amountCents), true],
      ["Moneda", "PEN · Sol peruano"],
    ]),
    showCancelButton: true,
    reverseButtons: true,
    confirmButtonText: "Confirmar y enviar",
    cancelButtonText: "Editar",
  });
  if (!isConfirmed || activePaymentAttempt) return;

  activePaymentAttempt = { idempotencyKey: crypto.randomUUID(), payload, recipientLabel: recipient.label };
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

recipientInput.addEventListener("input", scheduleRecipientLookup);
paymentForm.addEventListener("reset", () => {
  clearRecipient();
  setFieldError("recipient", "");
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

downloadReceiptButton.addEventListener("click", () => {
  if (receiptPaymentId) {
    void downloadReceiptPdf(receiptPaymentId, downloadReceiptButton);
  }
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
