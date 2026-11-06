// Interacciones mínimas: menú en celulares, confirmaciones y campos condicionales. Sin librerías externas.
document.addEventListener("DOMContentLoaded", function () {
  var boton = document.querySelector(".btn-menu");
  var menu = document.getElementById("menu");
  if (boton && menu) {
    var cerrar = function () {
      menu.classList.remove("abierto");
      boton.setAttribute("aria-expanded", "false");
    };
    boton.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var abierto = menu.classList.toggle("abierto");
      boton.setAttribute("aria-expanded", abierto ? "true" : "false");
    });
    document.addEventListener("click", function (ev) {
      if (menu.classList.contains("abierto") && !menu.contains(ev.target)) { cerrar(); }
    });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { cerrar(); } });
  }

  // Formularios que piden confirmación antes de enviarse (acciones irreversibles).
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (!window.confirm(form.getAttribute("data-confirmar"))) { ev.preventDefault(); }
    });
  });

  // Alerta de riesgo: el subtipo solo aplica a violencia o maltrato.
  var tipo = document.getElementById("id_tipo_situacion");
  var subtipo = document.getElementById("id_subtipo_violencia");
  if (tipo && subtipo) {
    var grupo = subtipo.closest(".grupo");
    var actualizar = function () {
      var aplica = tipo.value === "violencia_maltrato";
      grupo.style.display = aplica ? "" : "none";
      if (!aplica) { subtipo.value = ""; }
    };
    tipo.addEventListener("change", actualizar);
    actualizar();
  }

  // Ctrl+K (o Cmd+K) lleva al buscador de estudiantes, como en el prototipo.
  var buscador = document.getElementById("buscador-global");
  if (buscador) {
    document.addEventListener("keydown", function (ev) {
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === "k" || ev.key === "K")) { ev.preventDefault(); buscador.focus(); }
    });
  }

  // Menús desplegables (<details>): solo uno abierto a la vez; se cierran al hacer clic fuera o con Escape.
  var desplegables = document.querySelectorAll("details.filtro-barra, details.menu-fila, details.desplegable");
  desplegables.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) { desplegables.forEach(function (o) { if (o !== d) { o.open = false; } }); }
    });
  });
  document.addEventListener("click", function (ev) {
    desplegables.forEach(function (d) { if (d.open && !d.contains(ev.target)) { d.open = false; } });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { desplegables.forEach(function (d) { d.open = false; }); }
  });

  // Selectores que envían su formulario al cambiar (estudiante y periodo, filtros de pantalla).
  document.querySelectorAll("[data-autoenvio]").forEach(function (campo) {
    campo.addEventListener("change", function () { if (campo.form) { campo.form.submit(); } });
  });

  // «Seleccionar todos» en listas con casillas (cursos, estudiantes).
  document.querySelectorAll("[data-seleccionar-todos]").forEach(function (maestra) {
    var nombre = maestra.getAttribute("data-seleccionar-todos");
    var casillas = function () { return document.querySelectorAll('input[type=checkbox][name="' + nombre + '"]'); };
    var contador = document.querySelector('[data-contador="' + nombre + '"]');
    var actualizar = function () {
      var marcadas = Array.prototype.filter.call(casillas(), function (c) { return c.checked; }).length;
      if (contador) { contador.textContent = marcadas + (marcadas === 1 ? " seleccionado" : " seleccionados"); }
      maestra.checked = marcadas > 0 && marcadas === casillas().length;
      maestra.indeterminate = marcadas > 0 && marcadas < casillas().length;
    };
    maestra.addEventListener("change", function () {
      casillas().forEach(function (c) { c.checked = maestra.checked; });
      actualizar();
    });
    casillas().forEach(function (c) { c.addEventListener("change", actualizar); });
    actualizar();
  });

  // Situación conductual: el porcentaje solo se pide para registros de asistencia.
  var categoria = document.getElementById("id_categoria");
  var porcentaje = document.getElementById("id_porcentaje_asistencia");
  if (categoria && porcentaje) {
    var grupoPct = porcentaje.closest(".grupo");
    var verPct = function () {
      var aplica = categoria.value === "asistencia";
      grupoPct.style.display = aplica ? "" : "none";
      if (!aplica) { porcentaje.value = ""; }
    };
    categoria.addEventListener("change", verPct);
    verPct();
  }

  // Panel «Resumen» de los formularios por pasos: indica qué secciones están completas.
  var resumen = document.querySelector("[data-resumen-form]");
  if (resumen) {
    var form = document.getElementById(resumen.getAttribute("data-resumen-form"));
    var revisar = function () {
      resumen.querySelectorAll("[data-seccion]").forEach(function (dd) {
        var campos = (dd.getAttribute("data-campos") || "").split(" ").filter(Boolean);
        var llenos = campos.filter(function (n) {
          var els = form.querySelectorAll('[name="' + n + '"]');
          return Array.prototype.some.call(els, function (el) {
            if (el.type === "radio" || el.type === "checkbox") { return el.checked; }
            return (el.value || "").trim().length >= (parseInt(el.getAttribute("data-minimo") || "1", 10));
          });
        }).length;
        var total = campos.length;
        if (dd.hasAttribute("data-contar")) {
          dd.textContent = llenos + " de " + total;
        } else if (!dd.hasAttribute("data-fijo")) {
          dd.textContent = llenos === total ? "Completo" : "Pendiente";
          dd.classList.toggle("pendiente", llenos !== total);
        }
      });
    };
    if (form) {
      form.addEventListener("input", revisar);
      form.addEventListener("change", revisar);
      revisar();
    }
  }

  document.querySelectorAll("[data-imprimir]").forEach(function (b) {
    b.addEventListener("click", function () { window.print(); });
  });

  // Evita envíos dobles.
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (ev.defaultPrevented) { return; }
      var botones = Array.prototype.slice.call(form.querySelectorAll("button[type=submit]"));
      if (form.id) {
        botones = botones.concat(Array.prototype.slice.call(document.querySelectorAll('button[form="' + form.id + '"]')));
      }
      botones.forEach(function (b) {
        setTimeout(function () { b.disabled = true; }, 0);
      });
    });
  });
});
