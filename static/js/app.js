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

  // Avisos flotantes: los de éxito e información se cierran solos (pausa al pasar el mouse); los errores quedan.
  var cerrarAviso = function (t) {
    if (!t || t.classList.contains("saliendo")) { return; }
    t.classList.add("saliendo");
    setTimeout(function () {
      var cont = t.parentNode; t.remove();
      if (cont && !cont.children.length) { cont.remove(); }
    }, 230);
  };
  document.querySelectorAll(".toast").forEach(function (t, i) {
    t.querySelector(".toast-cerrar").addEventListener("click", function () { cerrarAviso(t); });
    if (t.classList.contains("error") || t.classList.contains("warning")) { return; }
    var restante = 6000 + i * 800, inicio, temporizador;
    t.style.setProperty("--duracion", restante + "ms");
    t.classList.add("con-tiempo");
    var correr = function () { inicio = Date.now(); temporizador = setTimeout(function () { cerrarAviso(t); }, restante); };
    t.addEventListener("mouseenter", function () { clearTimeout(temporizador); restante -= Date.now() - inicio; });
    t.addEventListener("mouseleave", correr);
    correr();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { document.querySelectorAll(".toast").forEach(cerrarAviso); }
  });

  // Confirmación de acciones irreversibles con un diálogo propio (sin el cuadro del navegador).
  var dialogo = null;
  var confirmar = function (mensaje, peligro, alAceptar) {
    if (!window.HTMLDialogElement) { if (window.confirm(mensaje)) { alAceptar(); } return; }
    if (!dialogo) {
      dialogo = document.createElement("dialog");
      dialogo.className = "confirmacion";
      dialogo.setAttribute("aria-labelledby", "confirmacion-titulo");
      dialogo.innerHTML = '<div class="confirmacion-cuerpo"><span class="confirmacion-icono" aria-hidden="true">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg></span>' +
        '<div><h2 id="confirmacion-titulo">¿Confirmar esta acción?</h2><p class="confirmacion-mensaje"></p></div></div>' +
        '<div class="confirmacion-pie"><button type="button" class="boton secundario" data-respuesta="no">Cancelar</button>' +
        '<button type="button" class="boton" data-respuesta="si">Confirmar</button></div>';
      document.body.appendChild(dialogo);
      dialogo.addEventListener("click", function (ev) { if (ev.target === dialogo) { dialogo.close("no"); } });
      dialogo.querySelectorAll("[data-respuesta]").forEach(function (b) {
        b.addEventListener("click", function () { dialogo.close(b.getAttribute("data-respuesta")); });
      });
    }
    dialogo.querySelector(".confirmacion-mensaje").textContent = mensaje;
    dialogo.classList.toggle("peligro", !!peligro);
    var aceptar = dialogo.querySelector('[data-respuesta="si"]');
    aceptar.className = "boton" + (peligro ? " peligro" : "");
    dialogo.onclose = function () { if (dialogo.returnValue === "si") { alAceptar(); } };
    dialogo.returnValue = "";
    dialogo.showModal();
    dialogo.querySelector('[data-respuesta="no"]').focus();
  };
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (form.dataset.confirmado === "1") { form.dataset.confirmado = ""; return; }
      ev.preventDefault();
      var boton = ev.submitter;
      confirmar(form.getAttribute("data-confirmar"), form.hasAttribute("data-peligro"), function () {
        form.dataset.confirmado = "1";
        if (form.requestSubmit) { form.requestSubmit(boton || undefined); } else { form.submit(); }
      });
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
