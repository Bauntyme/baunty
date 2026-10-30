/* 🌐 Mini App tili: uz (asl), ru, en.
   Til: localStorage «zk_lang» → Telegram language_code → uz. Server (/api/lang) bilan moslanadi.
   Avtomatik tarjima: Lug'at (aniq matn → tarjima) + qoidalar (regex). Ilova o'zbekcha chizadi,
   MutationObserver har yangi matn tugunini, placeholder/title'ni va Telegram oynalarini lug'at bo'yicha almashtiradi.
   Kodda to'g'ridan-to'g'ri: ZK_T("o'zbekcha", "русский", "english"). */
(function () {
  "use strict";
  var LANGS = {uz: 1, ru: 1, en: 1};
  var lang = "";
  try { lang = localStorage.getItem("zk_lang") || ""; } catch (e) {}
  try { var q = new URLSearchParams(location.search).get("lang"); if (q && LANGS[q]) lang = q; } catch (e) {}
  if (!LANGS[lang]) {
    var c = "";
    try { c = (window.Telegram.WebApp.initDataUnsafe.user.language_code || "").slice(0, 2).toLowerCase(); } catch (e) {}
    lang = /^(ru|uk|be|kk|ky|tg)$/.test(c) ? "ru" : c === "en" ? "en" : "uz";
  }
  window.ZK_LANG = lang;
  document.documentElement.lang = lang;
  window.ZK_T = function (uz, ru, en) {
    if (lang === "ru" && ru != null) return ru;
    if (lang === "en" && en != null) return en;
    return uz;
  };
  window.ZK_LANG_NAMES = {uz: "🇺🇿 O'zbekcha", ru: "🇷🇺 Русский", en: "🇬🇧 English"};

  // Synchronize language with ALL API requests (Accept-Language and X-Lang headers)
  var origFetch = window.fetch;
  if (typeof origFetch === "function") {
    window.fetch = function (url, opts) {
      opts = opts || {};
      var curLang = window.ZK_LANG || lang || "uz";
      var h = opts.headers;
      if (typeof Headers !== "undefined" && h instanceof Headers) {
        if (!h.has("Accept-Language")) h.set("Accept-Language", curLang);
        if (!h.has("X-Lang")) h.set("X-Lang", curLang);
      } else if (Array.isArray(h)) {
        h.push(["Accept-Language", curLang]);
        h.push(["X-Lang", curLang]);
      } else {
        opts.headers = Object.assign({}, h || {}, {
          "Accept-Language": curLang,
          "X-Lang": curLang
        });
      }
      return origFetch.call(window, url, opts);
    };
  }

  window.ZK_setLang = function (l, noReload) {
    if (!LANGS[l]) return;
    try { localStorage.setItem("zk_lang", l); } catch (e) {}
    window.ZK_LANG = l;
    document.documentElement.lang = l;
    try {
      var btnTexts = document.querySelectorAll("#zkLangText, .zk-lang-code");
      for (var b = 0; b < btnTexts.length; b++) btnTexts[b].textContent = l.toUpperCase();
      var pills = document.querySelectorAll(".zk-lang-pill, .zk-lang-modal-opt");
      for (var i = 0; i < pills.length; i++) {
        var isCur = (pills[i].getAttribute("data-lang") || "").toLowerCase() === l;
        if (isCur) {
          pills[i].classList.add("on");
          pills[i].setAttribute("aria-checked", "true");
        } else {
          pills[i].classList.remove("on");
          pills[i].setAttribute("aria-checked", "false");
        }
      }
    } catch (e) {}
    var done = function () { if (!noReload && l !== lang) location.reload(); };
    var init = "";
    try { init = window.Telegram.WebApp.initData || ""; } catch (e) {}
    if (!init) { done(); return; }
    try {
      fetch("/api/lang", {method: "POST", headers: {"Content-Type": "application/json", "X-Init-Data": init},
        body: JSON.stringify({lang: l})}).then(done, done);
    } catch (e) { done(); }
  };

  window.ZK_openLangModal = function () {
    var bg = document.getElementById("zkLangModalBg");
    var m = document.getElementById("zkLangModal");
    var cur = (window.ZK_LANG || localStorage.getItem("zk_lang") || "uz").toLowerCase();
    var opts = document.querySelectorAll(".zk-lang-modal-opt");
    for (var i = 0; i < opts.length; i++) {
      var isCur = (opts[i].getAttribute("data-lang") || "").toLowerCase() === cur;
      if (isCur) {
        opts[i].classList.add("on");
        opts[i].setAttribute("aria-checked", "true");
      } else {
        opts[i].classList.remove("on");
        opts[i].setAttribute("aria-checked", "false");
      }
    }
    if (bg) bg.classList.add("open");
    if (m) m.classList.add("open");
  };

  window.ZK_closeLangModal = function () {
    var bg = document.getElementById("zkLangModalBg");
    var m = document.getElementById("zkLangModal");
    if (bg) bg.classList.remove("open");
    if (m) m.classList.remove("open");
  };

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" || e.keyCode === 27) {
      if (typeof window.ZK_closeLangModal === "function") window.ZK_closeLangModal();
    }
  });

  function syncLangUI() {
    var cur = (window.ZK_LANG || localStorage.getItem("zk_lang") || "uz").toLowerCase();
    var btnTexts = document.querySelectorAll("#zkLangText, .zk-lang-code");
    for (var b = 0; b < btnTexts.length; b++) btnTexts[b].textContent = cur.toUpperCase();
    var pills = document.querySelectorAll(".zk-lang-pill, .zk-lang-modal-opt");
    for (var i = 0; i < pills.length; i++) {
      var isCur = (pills[i].getAttribute("data-lang") || "").toLowerCase() === cur;
      if (isCur) {
        pills[i].classList.add("on");
        pills[i].setAttribute("aria-checked", "true");
      } else {
        pills[i].classList.remove("on");
        pills[i].setAttribute("aria-checked", "false");
      }
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncLangUI);
  } else {
    syncLangUI();
  }

  var DICT_RU = {
    // Navigatsiya & Bo'limlar
    "Kinolar": "Фильмы",
    "🎬 Kinolar": "🎬 Фильмы",
    "Musiqa": "Музыка",
    "🎧 Musiqa": "🎧 Музыка",
    "Kitoblar": "Книги",
    "📚 Kitoblar": "📚 Книги",
    "O'yinlar": "Игры",
    "🧸 O'yinlar": "🧸 Игры",
    "Story": "Истории",
    "👻 Story": "👻 Истории",
    "Hujjatlar": "Документы",
    "📄 Hujjatlar": "📄 Документы",
    "Viktorina": "Викторина",
    "🧠 Viktorina": "🧠 Викторина",
    "Prava": "ПДД",
    "🚗 Prava": "🚗 ПДД",
    "Taomlar": "Рецепты",
    "🍲 Taomlar": "🍲 Рецепты",
    "Kurs": "Курсы",
    "💱 Kurs": "💱 Курсы",
    "Mafia": "Мафия",
    "🕵️ Mafia": "🕵️ Мафия",
    "Tv Xona": "ТВ Комната",
    "📺 Tv Xona": "📺 ТВ Комната",
    "Rasxod": "Расходы",
    "💰 Rasxod": "💰 Расходы",
    "Kaloriya": "Калории",
    "🥗 Kaloriya": "🥗 Калории",
    "TV": "ТВ",
    "📺 TV": "📺 ТВ",
    "📢 Kanal": "📢 Канал",
    "Kanal": "Канал",

    // Sarlavha & Filtrlar
    "Yuklanmoqda…": "Загрузка…",
    "Yuklanmoqda...": "Загрузка...",
    "Yuklanmoqda": "Загрузка",
    "Hammasi": "Все",
    "🔥 Ommabop": "🔥 Популярные",
    "Ommabop": "Популярные",
    "🎬 Filmlar": "🎬 Фильмы",
    "Filmlar": "Фильмы",
    "📺 Seriallar": "📺 Сериалы",
    "Seriallar": "Сериалы",
    "🧸 Multfilmlar": "🧸 Мультфильмы",
    "Multfilmlar": "Мультфильмы",
    "🎌 Anime": "🎌 Аниме",
    "Anime": "Аниме",
    "✓ Ko'rganlarim": "✓ Просмотренные",
    "Ko'rganlarim": "Просмотренные",
    "🆕 Yangi qo'shilganlar": "🆕 Новинки",
    "Yangi qo'shilganlar": "Новинки",
    "Kino nomi yoki kodi…": "Название или код фильма…",
    "Kino nomi yoki kodi...": "Название или код фильма...",
    "Tozalash": "Очистить",
    "Tasodifiy kino tanlash": "Случайный фильм",
    "Tasodifiy kino": "Случайный фильм",
    "Tilni tanlash / Сменить язык": "Сменить язык / Switch language",
    "Til tanlash / Choose language": "Выбор языка",
    "Til tanlash": "Выбор языка",

    // Natijalar & Matnlar
    "Natijalar": "Результаты",
    "ta": "шт",
    "Hech narsa topilmadi": "Ничего не найдено",
    "Boshqa nom bilan qidirib ko'ring yoki kino kodini botga yuboring.": "Попробуйте поискать по другому названию или отправьте код фильма боту.",
    "Hali hech narsa ko'rmadingiz": "Вы ещё ничего не смотрели",
    "Kino tanlang — u shu yerda belgilanib boradi.": "Выберите фильм — он появится здесь.",
    "Hozircha bo'sh": "Пока пусто",
    "eng ko'p ko'rilgan": "самые просматриваемые",
    "Tomosha qilish": "Смотреть",
    "▶️ Tomosha qilish": "▶️ Смотреть",
    "Qismlar": "Серии",
    "📺 Qismlar": "📺 Серии",
    "Ko'proq…": "Подробнее…",
    "Ko'proq...": "Подробнее...",
    "Ko'proq": "Подробнее",
    "Qisqaroq": "Скрыть",
    "qism": "серия",
    "Kod:": "Код:",
    "🔑 Kod:": "🔑 Код:",
    "🔒 Bir qadam qoldi": "🔒 Остался один шаг",
    "Kinoni olish uchun quyidagi kanal(lar)ga a'zo bo'ling, so'ng «Tekshirish» ni bosing.": "Чтобы получить фильм, подпишитесь на канал(ы) ниже и нажмите «Проверить».",
    "A'zo bo'lish ›": "Подписаться ›",
    "✅ A'zo bo'ldim — tekshirish": "✅ Я подписался — проверить",
    "Tekshirish": "Проверить",
    "A'zo bo'lish": "Подписаться",
    "📱 Kinoni olish uchun katalogni Telegram ichida oching": "📱 Чтобы получить фильм, откройте каталог в Telegram",
    "✅ Kino chatga yuborildi": "✅ Фильм отправлен в чат",
    "⏳ Kino navbatda — bir necha soniyada chatga keladi": "⏳ Фильм в очереди — скоро появится в чате",
    "❌ Bu kino olib tashlangan": "❌ Этот фильм был удален",
    "⚠️ Sessiya eskirgan — katalogni yopib, qayta oching": "⚠️ Сессия устарела — закройте и откройте каталог заново",
    "📶 Internet bilan muammo. Qayta urinib ko'ring": "📶 Проблема с интернетом. Попробуйте еще раз",
    "⚠️ Yuborib bo'lmadi. Birozdan keyin urinib ko'ring": "⚠️ Не удалось отправить. Попробуйте чуть позже",
    "⏳ Hozir juda ko'p odam kirdi — 5-10 soniyadan keyin qayta bosing": "⏳ Высокая нагрузка — повторите через 5-10 секунд",
    "🤖 Botni ishga tushiryapmiz…": "🤖 Запускаем бота…",
    "Aylantirish": "Крутить",
    "Yopish": "Закрыть",
    "kino · musiqa · kitob · o'yin · story": "кино · музыка · книги · игры · истории",

    // Umumiy harakatlar
    "Saqlash": "Сохранить",
    "Bekor qilish": "Отмена",
    "O'chirish": "Удалить",
    "Ha": "Да",
    "Yo'q": "Нет",
    "Orqaga": "Назад",
    "Bosh sahifa": "Главная",
    "Batafsil": "Подробнее",
    "Ulashish": "Поделиться",
    "Nusxa olish": "Скопировать",
    "Nusxalandi": "Скопировано",
    "Barchasi": "Все",
    "Boshlash": "Начать",
    "O'yin": "Игра",
    "Savol": "Вопрос",
    "Javob": "Ответ",
    "Natija": "Результат",
    "Ball": "Баллы",
    "Qayta boshlash": "Начать заново",
    "Keyingi": "Следующий",
    "Oldingi": "Предыдущий",
    "Xona": "Комната",
    "Ulanish": "Подключиться",
    "Yaratish": "Создать",
    "Xona kodi": "Код комнаты",
    "Valyuta": "Валюта",
    "Sotish": "Продажа",
    "Sotib olish": "Покупка",
    "Markaziy bank kursi": "Курс ЦБ",
    "Qidirish": "Поиск",
    "Qo'shiq yoki ijrochi nomi…": "Название песни или артист…",
    "Qo'shiq yoki ijrochi nomi...": "Название песни или артист...",
    "Kitob nomi yoki muallif…": "Название книги или автор…",
    "Kitob nomi yoki muallif...": "Название книги или автор...",
    "Tanlanganlar": "Избранное",
    "Mening qo'shiqlarim": "Мои треки",
    "Treklar": "Треки",
    "Ijrochilar": "Исполнители",
    "Albomlar": "Альбомы",
    "Yuklab olish": "Скачать",
    "Tinglash": "Слушать",
    "Badiiy": "Художественная",
    "Biznes": "Бизнес",
    "Psixologiya": "Психология",
    "Diniy": "Религия",
    "O'qish": "Читать",
    "Do'stlar bilan birga tomosha qiling": "Смотрите вместе с друзьями",
    "Xona yaratish": "Создать комнату",
    "Xonaga kirish": "Войти в комнату",
    "Biletlar": "Билеты",
    "Mavzular": "Темы",
    "Imtihon": "Экзамен",
    "Xatolar ustida ishlash": "Работа над ошибками",
    "To'g'ri": "Правильно",
    "Noto'g'ri": "Неправильно",
    "Natijangiz": "Ваш результат",
    "Qayta urinish": "Попробовать снова",
    "Keyingi savol": "Следующий вопрос",
    "Jonli efir": "Прямой эфир",
    "Barcha kanallar": "Все каналы",
    "O'zbekiston": "Узбекистан",
    "Rossiya": "Россия",
    "Sport": "Спорт",
    "Yangiliklar": "Новости",
    "Bolalar": "Детские",
    "Musiqiy": "Музыкальные",
    "Masalliqlar": "Ингредиенты",
    "Tayyorlanishi": "Приготовление",
    "Vaqt": "Время",
    "Kkal": "Ккал",
    "Kalkulyator": "Калькулятор",
    "Markaziy Bank": "Центральный Банк",
    "Bo'limlar": "Разделы",
    "Barcha bo'limlar": "Все разделы",
    "Botni qo'llab-quvvatlash": "Поддержать бота",
    "Har bir yordam bot rivojiga ketadi.": "Каждая поддержка помогает развитию бота.",
    "nusxa": "копия",
    "Nusxalandi": "Скопировано",
    "✓ Nusxalandi": "✓ Скопировано",
    "O'zbekcha": "Узбекский",
    "Русский": "Русский",
    "English": "Английский"
  };

  var RULES_RU = [
    [/▶️\s*(\d+)-qismni ko'rish/i, "▶️ Смотреть $1-ю серию"],
    [/(\d+)-qismni ko'rish/i, "Смотреть $1-ю серию"],
    [/(\d+)-qism chatga yuborildi/i, "Серия $1 отправлена в чат"],
    [/(\d+)-qism navbatda/i, "Серия $1 в очереди"],
    [/(\d+)\s*qism/i, "$1 серий"],
    [/(\d+)-qism/i, "$1-я серия"],
    [/(\d+)\s*ta\b/i, "$1 шт"],
    [/Top\s*(\d+)/i, "Топ $1"],
    [/(\d+)-savol/i, "Вопрос $1"],
    [/(\d+)-bilet/i, "Билет $1"],
    [/(\d+)-fasl/i, "$1-й сезон"]
  ];

  var DICT_EN = {
    // Navigatsiya & Bo'limlar
    "Kinolar": "Movies",
    "🎬 Kinolar": "🎬 Movies",
    "Musiqa": "Music",
    "🎧 Musiqa": "🎧 Music",
    "Kitoblar": "Books",
    "📚 Kitoblar": "📚 Books",
    "O'yinlar": "Games",
    "🧸 O'yinlar": "🧸 Games",
    "Story": "Stories",
    "👻 Story": "👻 Stories",
    "Hujjatlar": "Documents",
    "📄 Hujjatlar": "📄 Documents",
    "Viktorina": "Quiz",
    "🧠 Viktorina": "🧠 Quiz",
    "Prava": "Driving",
    "🚗 Prava": "🚗 Driving",
    "Taomlar": "Recipes",
    "🍲 Taomlar": "🍲 Recipes",
    "Kurs": "Rates",
    "💱 Kurs": "💱 Rates",
    "Mafia": "Mafia",
    "🕵️ Mafia": "🕵️ Mafia",
    "Tv Xona": "TV Room",
    "📺 Tv Xona": "📺 TV Room",
    "Rasxod": "Expenses",
    "💰 Rasxod": "💰 Expenses",
    "Kaloriya": "Calories",
    "🥗 Kaloriya": "🥗 Calories",
    "TV": "TV",
    "📺 TV": "📺 TV",
    "📢 Kanal": "📢 Channel",
    "Kanal": "Channel",

    // Sarlavha & Filtrlar
    "Yuklanmoqda…": "Loading…",
    "Yuklanmoqda...": "Loading...",
    "Yuklanmoqda": "Loading",
    "Hammasi": "All",
    "🔥 Ommabop": "🔥 Popular",
    "Ommabop": "Popular",
    "🎬 Filmlar": "🎬 Movies",
    "Filmlar": "Movies",
    "📺 Seriallar": "📺 TV Series",
    "Seriallar": "TV Series",
    "🧸 Multfilmlar": "🧸 Cartoons",
    "Multfilmlar": "Cartoons",
    "🎌 Anime": "🎌 Anime",
    "Anime": "Anime",
    "✓ Ko'rganlarim": "✓ Watched",
    "Ko'rganlarim": "Watched",
    "🆕 Yangi qo'shilganlar": "🆕 New releases",
    "Yangi qo'shilganlar": "New releases",
    "Kino nomi yoki kodi…": "Movie title or code…",
    "Kino nomi yoki kodi...": "Movie title or code...",
    "Tozalash": "Clear",
    "Tasodifiy kino tanlash": "Pick random movie",
    "Tasodifiy kino": "Random movie",
    "Tilni tanlash / Сменить язык": "Change language",
    "Til tanlash / Choose language": "Choose language",
    "Til tanlash": "Choose language",

    // Natijalar & Matnlar
    "Natijalar": "Results",
    "ta": "items",
    "Hech narsa topilmadi": "Nothing found",
    "Boshqa nom bilan qidirib ko'ring yoki kino kodini botga yuboring.": "Try searching with a different name or send movie code to bot.",
    "Hali hech narsa ko'rmadingiz": "You haven't watched anything yet",
    "Kino tanlang — u shu yerda belgilanib boradi.": "Select a movie — it will appear here.",
    "Hozircha bo'sh": "Empty for now",
    "eng ko'p ko'rilgan": "most watched",
    "Tomosha qilish": "Watch",
    "▶️ Tomosha qilish": "▶️ Watch",
    "Qismlar": "Episodes",
    "📺 Qismlar": "📺 Episodes",
    "Ko'proq…": "More…",
    "Ko'proq...": "More...",
    "Ko'proq": "More",
    "Qisqaroq": "Less",
    "qism": "episode",
    "Kod:": "Code:",
    "🔑 Kod:": "🔑 Code:",
    "🔒 Bir qadam qoldi": "🔒 One step left",
    "Kinoni olish uchun quyidagi kanal(lar)ga a'zo bo'ling, so'ng «Tekshirish» ni bosing.": "To get the movie, subscribe to the channel(s) below, then click «Check».",
    "A'zo bo'lish ›": "Subscribe ›",
    "✅ A'zo bo'ldim — tekshirish": "✅ I subscribed — check",
    "Tekshirish": "Check",
    "A'zo bo'lish": "Subscribe",
    "📱 Kinoni olish uchun katalogni Telegram ichida oching": "📱 Open catalog inside Telegram to get the movie",
    "✅ Kino chatga yuborildi": "✅ Movie sent to chat",
    "⏳ Kino navbatda — bir necha soniyada chatga keladi": "⏳ Movie in queue — arriving shortly in chat",
    "❌ Bu kino olib tashlangan": "❌ This movie has been removed",
    "⚠️ Sessiya eskirgan — katalogni yopib, qayta oching": "⚠️ Session expired — close and reopen catalog",
    "📶 Internet bilan muammo. Qayta urinib ko'ring": "📶 Network problem. Please try again",
    "⚠️ Yuborib bo'lmadi. Birozdan keyin urinib ko'ring": "⚠️ Failed to send. Please try again later",
    "⏳ Hozir juda ko'p odam kirdi — 5-10 soniyadan keyin qayta bosing": "⏳ High load — please retry in 5-10 seconds",
    "🤖 Botni ishga tushiryapmiz…": "🤖 Starting bot…",
    "Aylantirish": "Spin",
    "Yopish": "Close",
    "kino · musiqa · kitob · o'yin · story": "movies · music · books · games · stories",

    // Umumiy harakatlar
    "Saqlash": "Save",
    "Bekor qilish": "Cancel",
    "O'chirish": "Delete",
    "Ha": "Yes",
    "Yo'q": "No",
    "Orqaga": "Back",
    "Bosh sahifa": "Home",
    "Batafsil": "Details",
    "Ulashish": "Share",
    "Nusxa olish": "Copy",
    "Nusxalandi": "Copied",
    "Barchasi": "All",
    "Boshlash": "Start",
    "O'yin": "Game",
    "Savol": "Question",
    "Javob": "Answer",
    "Natija": "Result",
    "Ball": "Score",
    "Qayta boshlash": "Restart",
    "Keyingi": "Next",
    "Oldingi": "Previous",
    "Xona": "Room",
    "Ulanish": "Connect",
    "Yaratish": "Create",
    "Xona kodi": "Room code",
    "Valyuta": "Currency",
    "Sotish": "Sell",
    "Sotib olish": "Buy",
    "Markaziy bank kursi": "Central Bank Rate",
    "Qidirish": "Search",
    "Qo'shiq yoki ijrochi nomi…": "Song or artist name…",
    "Qo'shiq yoki ijrochi nomi...": "Song or artist name...",
    "Kitob nomi yoki muallif…": "Book title or author…",
    "Kitob nomi yoki muallif...": "Book title or author...",
    "Tanlanganlar": "Favorites",
    "Mening qo'shiqlarim": "My tracks",
    "Treklar": "Tracks",
    "Ijrochilar": "Artists",
    "Albomlar": "Albums",
    "Yuklab olish": "Download",
    "Tinglash": "Listen",
    "Badiiy": "Fiction",
    "Biznes": "Business",
    "Psixologiya": "Psychology",
    "Diniy": "Religion",
    "O'qish": "Read",
    "Do'stlar bilan birga tomosha qiling": "Watch together with friends",
    "Xona yaratish": "Create room",
    "Xonaga kirish": "Join room",
    "Biletlar": "Tickets",
    "Mavzular": "Topics",
    "Imtihon": "Exam",
    "Xatolar ustida ishlash": "Review errors",
    "To'g'ri": "Correct",
    "Noto'g'ri": "Incorrect",
    "Natijangiz": "Your result",
    "Qayta urinish": "Try again",
    "Keyingi savol": "Next question",
    "Jonli efir": "Live Stream",
    "Barcha kanallar": "All channels",
    "O'zbekiston": "Uzbekistan",
    "Rossiya": "Russia",
    "Sport": "Sports",
    "Yangiliklar": "News",
    "Bolalar": "Kids",
    "Musiqiy": "Music",
    "Masalliqlar": "Ingredients",
    "Tayyorlanishi": "Preparation",
    "Vaqt": "Time",
    "Kkal": "Kcal",
    "Kalkulyator": "Calculator",
    "Markaziy Bank": "Central Bank",
    "Bo'limlar": "Sections",
    "Barcha bo'limlar": "All sections",
    "Botni qo'llab-quvvatlash": "Support the bot",
    "Har bir yordam bot rivojiga ketadi.": "Every contribution supports bot development.",
    "nusxa": "copy",
    "Nusxalandi": "Copied",
    "✓ Nusxalandi": "✓ Copied",
    "O'zbekcha": "Uzbek",
    "Русский": "Russian",
    "English": "English"
  };

  var RULES_EN = [
    [/▶️\s*(\d+)-qismni ko'rish/i, "▶️ Watch episode $1"],
    [/(\d+)-qismni ko'rish/i, "Watch episode $1"],
    [/(\d+)-qism chatga yuborildi/i, "Episode $1 sent to chat"],
    [/(\d+)-qism navbatda/i, "Episode $1 in queue"],
    [/(\d+)\s*qism/i, "$1 episodes"],
    [/(\d+)-qism/i, "Episode $1"],
    [/(\d+)\s*ta\b/i, "$1 items"],
    [/Top\s*(\d+)/i, "Top $1"],
    [/(\d+)-savol/i, "Question $1"],
    [/(\d+)-bilet/i, "Ticket $1"],
    [/(\d+)-fasl/i, "Season $1"]
  ];

  var D = {}, R = [], ready = false;

  function tr(s) {
    if (!s || s.length > 500) return null;
    var t = s.trim();
    if (!t) return null;
    var v = D[t];
    if (v == null) {
      for (var i = 0; i < R.length; i++) {
        if (R[i][0].test(t)) { v = t.replace(R[i][0], R[i][1]); break; }
      }
      if (v == null) return null;
    }
    return t === s ? v : s.replace(t, function () { return v; });
  }

  window.ZK_tr = function (s) {
    var v = ready ? tr(String(s)) : null;
    return v == null ? s : v;
  };

  var ATTRS = ["placeholder", "title", "aria-label", "data-ph"];

  function walk(n) {
    if (!n) return;
    if (n.nodeType === 3) {
      var v = tr(n.nodeValue);
      if (v != null && v !== n.nodeValue) n.nodeValue = v;
      return;
    }
    if (n.nodeType !== 1) return;
    var tg = n.tagName;
    if (tg === "SCRIPT" || tg === "STYLE" || tg === "TEXTAREA" || tg === "svg" || n.isContentEditable) return;
    if (n.hasAttribute && n.hasAttribute("data-notr")) return;
    for (var a = 0; a < ATTRS.length; a++) {
      var av = n.getAttribute(ATTRS[a]);
      if (av) { var w = tr(av); if (w != null && w !== av) n.setAttribute(ATTRS[a], w); }
    }
    if (tg === "INPUT" && (n.type === "button" || n.type === "submit") && n.value) {
      var iv = tr(n.value); if (iv != null) n.value = iv;
    }
    for (var ch = n.firstChild; ch; ch = ch.nextSibling) walk(ch);
  }

  function hookTelegram() {
    var W;
    try { W = window.Telegram.WebApp; } catch (e) { return; }
    if (!W) return;
    var wrap = function (name, fix) {
      var f = W[name];
      if (typeof f !== "function") return;
      W[name] = function () { var a = Array.prototype.slice.call(arguments); fix(a); return f.apply(W, a); };
    };
    var T = window.ZK_tr;
    wrap("showAlert", function (a) { a[0] = T(a[0]); });
    wrap("showConfirm", function (a) { a[0] = T(a[0]); });
    wrap("showPopup", function (a) {
      var p = a[0];
      if (p && typeof p === "object") {
        p = Object.assign({}, p);
        if (p.title) p.title = T(p.title);
        if (p.message) p.message = T(p.message);
        if (p.buttons) p.buttons = p.buttons.map(function (b) { return b && b.text ? Object.assign({}, b, {text: T(b.text)}) : b; });
        a[0] = p;
      }
    });
    var MB = W.MainButton;
    if (MB && typeof MB.setText === "function") {
      var st = MB.setText;
      MB.setText = function (t) { return st.call(MB, T(t)); };
      if (typeof MB.setParams === "function") {
        var sp = MB.setParams;
        MB.setParams = function (p) { if (p && p.text) p = Object.assign({}, p, {text: T(p.text)}); return sp.call(MB, p); };
      }
    }
  }

  var oa = window.alert, oc = window.confirm;
  if (oa) window.alert = function (m) { return oa.call(window, window.ZK_tr(m)); };
  if (oc) window.confirm = function (m) { return oc.call(window, window.ZK_tr(m)); };

  window.ZK_DICT_LOAD = function (dict, rules) {
    D = dict || {};
    R = (rules || []).map(function (r) { return [new RegExp(r[0]), r[1]]; });
    ready = true;
    hookTelegram();
    walk(document.documentElement);
    try {
      new MutationObserver(function (ms) {
        for (var i = 0; i < ms.length; i++) {
          var m = ms[i];
          if (m.type === "characterData") { walk(m.target); continue; }
          if (m.type === "attributes") {
            if (m.target.nodeType === 1) {
              var av = m.target.getAttribute(m.attributeName);
              var w = tr(av);
              if (w != null && w !== av) m.target.setAttribute(m.attributeName, w);
            }
            continue;
          }
          for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
        }
      }).observe(document.documentElement, {
        childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ATTRS
      });
    } catch (e) {}
    try { document.title = window.ZK_tr(document.title); } catch (e) {}
  };

  // Faol til bo'yicha lug'atni avtomatik yuklash
  if (lang === "ru") {
    window.ZK_DICT_LOAD(DICT_RU, RULES_RU);
  } else if (lang === "en") {
    window.ZK_DICT_LOAD(DICT_EN, RULES_EN);
  } else {
    hookTelegram();
  }

  // DOM to'liq yuklangach, yana bir bor sahifani aylanish
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      if (ready) walk(document.documentElement);
    });
  }
})();
