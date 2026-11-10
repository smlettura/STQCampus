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

// Buscadores con lista desplegable: los campos con data-sugerencias="<url>" piden coincidencias a medida que se
// escribe (desde 2 letras) y muestran una lista navegable con el teclado. Al elegir, se va a la ficha del resultado
// o, si el campo tiene data-destino="?estudiante={id}", a esa dirección. Enter sin elegir envía el formulario normal.
document.addEventListener("DOMContentLoaded", function () {
  var contador = 0;
  document.querySelectorAll("input[data-sugerencias]").forEach(function (campo) {
    var id = "sugerencias-" + (++contador);
    var lista = document.createElement("ul");
    lista.className = "sugerencias";
    lista.id = id;
    lista.setAttribute("role", "listbox");
    lista.hidden = true;
    var contenedor = campo.closest("form, label, .filtro-texto") || campo.parentNode;
    if (getComputedStyle(contenedor).position === "static") { contenedor.style.position = "relative"; }
    contenedor.appendChild(lista);
    campo.setAttribute("role", "combobox");
    campo.setAttribute("aria-autocomplete", "list");
    campo.setAttribute("aria-controls", id);
    campo.setAttribute("aria-expanded", "false");

    var items = [], activo = -1, temporizador = null, ultima = "", pedido = 0;

    function cerrar() {
      lista.hidden = true; activo = -1;
      campo.setAttribute("aria-expanded", "false");
      campo.removeAttribute("aria-activedescendant");
    }
    function destino(r) {
      var plantilla = campo.getAttribute("data-destino");
      return plantilla ? plantilla.replace("{id}", encodeURIComponent(r.id)) : r.url;
    }
    function marcar(i) {
      var opciones = lista.querySelectorAll("li[role=option]");
      opciones.forEach(function (li, k) { li.setAttribute("aria-selected", k === i ? "true" : "false"); });
      activo = i;
      if (i >= 0 && opciones[i]) {
        campo.setAttribute("aria-activedescendant", opciones[i].id);
        opciones[i].scrollIntoView({ block: "nearest" });
      }
    }
    function pintar(resultados, texto) {
      items = resultados;
      lista.innerHTML = "";
      if (!resultados.length) {
        var vacio = document.createElement("li");
        vacio.className = "sugerencias-vacio";
        vacio.textContent = "Sin coincidencias para «" + texto + "»";
        lista.appendChild(vacio);
      }
      resultados.forEach(function (r, k) {
        var li = document.createElement("li");
        li.id = id + "-" + k;
        li.setAttribute("role", "option");
        var t = document.createElement("strong"); t.textContent = r.texto;
        var d = document.createElement("small"); d.textContent = r.detalle || "";
        li.appendChild(t); li.appendChild(d);
        li.addEventListener("mousedown", function (ev) { ev.preventDefault(); window.location.href = destino(r); });
        li.addEventListener("mousemove", function () { marcar(k); });
        lista.appendChild(li);
      });
      lista.hidden = false; activo = -1;
      campo.setAttribute("aria-expanded", "true");
    }
    function buscar() {
      var texto = campo.value.trim();
      if (texto.length < 2) { cerrar(); ultima = texto; return; }
      if (texto === ultima && !lista.hidden) { return; }
      ultima = texto;
      var url = new URL(campo.getAttribute("data-sugerencias"), window.location.href);
      url.searchParams.set("q", texto);
      var numero = ++pedido;
      fetch(url.toString(), { headers: { "Accept": "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : { resultados: [] }; })
        .then(function (datos) { if (numero === pedido && campo.value.trim() === texto) { pintar(datos.resultados || [], texto); } })
        .catch(function () { cerrar(); });
    }
    campo.addEventListener("input", function () { clearTimeout(temporizador); temporizador = setTimeout(buscar, 180); });
    campo.addEventListener("focus", function () { if (campo.value.trim().length >= 2) { ultima = ""; buscar(); } });
    campo.addEventListener("blur", function () { setTimeout(cerrar, 120); });
    campo.addEventListener("keydown", function (ev) {
      if (lista.hidden || !items.length) { if (ev.key === "Escape") { cerrar(); } return; }
      if (ev.key === "ArrowDown") { ev.preventDefault(); marcar(Math.min(activo + 1, items.length - 1)); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); marcar(Math.max(activo - 1, 0)); }
      else if (ev.key === "Enter" && activo >= 0) { ev.preventDefault(); window.location.href = destino(items[activo]); }
      else if (ev.key === "Escape") { cerrar(); }
    });
  });
});
