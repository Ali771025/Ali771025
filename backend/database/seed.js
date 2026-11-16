/**
 * Seed script — populates catalog data (brands, appliance types, faults,
 * provinces/cities, technicians) and an admin user.
 * Run: node database/seed.js
 */
require('dotenv').config({ path: require('path').join(__dirname, '../.env') });
const bcrypt = require('bcryptjs');
const {
  sequelize, User, Brand, ApplianceType, FaultCategory, Province, City, Technician, ApplianceTypeFault,
} = require('../src/models');

const brands = [
  ['سامسونگ', 'Samsung', 'samsung'], ['ال‌جی', 'LG', 'lg'], ['اسنوا', 'Snowa', 'snowa'],
  ['بوش', 'Bosch', 'bosch'], ['سیمنز', 'Siemens', 'siemens'], ['هیتاچی', 'Hitachi', 'hitachi'],
  ['دوو', 'Daewoo', 'daewoo'], ['جی‌پلاس', 'G-Plus', 'g-plus'], ['ایستکو', 'Eastco', 'eastco'],
  ['امیر', 'Amir', 'amir'], ['هایسنس', 'Hisense', 'hisense'], ['مبتین', 'Mobin', 'mobin'],
  ['کنوود', 'Kenwood', 'kenwood'], ['اسکانتل', 'Scantail', 'scantail'], ['پارس', 'Pars', 'pars'],
];

const applianceTypes = [
  ['یخچال فریزر', 'refrigerator-freezer', 'refrigerator', 'یخچال فریزرهای دو درب و چند درب'],
  ['ساید بای ساید', 'side-by-side', 'refrigerator', 'یخچال‌های ساید بای ساید مدرن'],
  ['فریزر', 'freezer', 'refrigerator', 'فریزرهای صندوقی و ایستاده'],
  ['لباسشویی', 'washing-machine', 'washing_machine', 'ماشین لباسشویی اتوماتیک و دوقلو'],
  ['ماشین ظرفشویی', 'dishwasher', 'dishwasher', 'ظرفشویی‌های ۱۲ و ۱۴ نفره'],
  ['یخچال نمایشگاهی', 'display-fridge', 'refrigerator', 'سردخانه و یخچال ویترینی'],
];

const faults = [
  ['سرد نکردن یخچال', 'not-cooling', 'یخچال خنک نمی‌کند یا ضعیف خنک می‌کند', true],
  ['یخ زدن بیش از حد / برفک', 'excess-frost', 'تجمع برفک در فریزر یا دیواره‌ها', true],
  ['نشت آب زیر یخچال', 'water-leak', 'آبریزی داخل یا زیر دستگاه', true],
  ['خرابی موتور/کمپرسور', 'compressor-failure', 'صدای غیرعادی یا کار نکردن موتور', true],
  ['خرابی برد الکترونیکی', 'board-failure', 'ارور روی نمایشگر یا کار نکردن برد', true],
  ['خرابی ترموستات', 'thermostat-failure', 'دمای نامتعادل مخازن', false],
  ['نشت گاز مبرد', 'refrigerant-leak', 'نیاز به شارژ گاز و رفع نشتی', true],
  ['خرابی واشر و درب', 'door-gasket', 'بسته نشدن صحیح درب', false],
  ['نچرخیدن دیگ لباسشویی', 'drum-not-rotating', 'دیگ حرکت نمی‌کند', true],
  ['تکان و صدای شدید لباسشویی', 'excessive-vibration', 'لرزش شدید هنگام خشک کردن', true],
  ['تخلیه نشدن آب', 'drain-failure', 'آب داخل مخزن باقی می‌ماند', true],
  ['خطای قفل درب', 'door-lock-error', 'درب باز یا قفل نمی‌شود', false],
  ['خرابی پمپ ظرفشویی', 'pump-failure', 'آب‌رسانی یا تخلیه مختل شده', false],
  ['تمیز نشستن ظروف', 'poor-washing', 'چربی و باقیمانده غذا', false],
  ['نشتی آب ظرفشویی', 'dishwasher-leak', 'آبریزی از کف دستگاه', false],
  ['خرابی المنت خشک‌کن', 'heater-failure', 'ظروف خشک خارج نمی‌شوند', false],
  ['نصب و راه‌اندازی', 'installation', 'نصب اولیه، اتصالات آب و فیلتر', true],
];

const geo = {
  تهران: ['تهران', 'شهرری', 'کرج', 'اسلامشهر', 'ورامین', 'پاکدشت', 'رباط‌کریم'],
  اصفهان: ['اصفهان', 'کاشان', 'نجف‌آباد', 'شاهین‌شهر', 'خمینی‌شهر'],
  فارس: ['شیراز', 'مرودشت', 'جهرم', 'فسا'],
  خراسانرضوی: ['مشهد', 'نیشابور', 'سبزوار', 'تربت حیدریه'],
  آذربایجانشرقی: ['تبریز', 'مراغه', 'مرند', 'اهر'],
  البرز: ['کرج', 'فردیس', 'نظرآباد'],
  قزوین: ['قزوین', 'تاکستان', 'آبیک'],
  مازندران: ['ساری', 'بابل', 'آمل', 'قائم‌شهر'],
  گیلان: ['رشت', 'لاهیجان', 'انزلی', 'لنگرود'],
  خوزستان: ['اهواز', 'دزفول', 'آبادان', 'خرمشهر'],
};

const technicians = [
  ['رضا محمدی', '09121110001', 4.8, ['refrigerator-freezer', 'side-by-side']],
  ['علی کریمی', '09121110002', 4.6, ['washing-machine', 'dishwasher']],
  ['حسین احمدی', '09121110003', 4.9, ['refrigerator-freezer', 'freezer', 'side-by-side']],
  ['مهدی رضایی', '09121110004', 4.7, ['dishwasher', 'washing-machine']],
  ['امیر حسینی', '09121110005', 4.5, ['refrigerator-freezer', 'display-fridge']],
];

/* which faults belong to which appliance category */
const faultMap = {
  'refrigerator-freezer': ['not-cooling', 'excess-frost', 'water-leak', 'compressor-failure', 'board-failure', 'thermostat-failure', 'refrigerant-leak', 'door-gasket', 'installation'],
  'side-by-side': ['not-cooling', 'excess-frost', 'water-leak', 'compressor-failure', 'board-failure', 'refrigerant-leak', 'door-gasket', 'installation'],
  freezer: ['not-cooling', 'excess-frost', 'compressor-failure', 'refrigerant-leak', 'thermostat-failure', 'installation'],
  'washing-machine': ['drum-not-rotating', 'excessive-vibration', 'drain-failure', 'door-lock-error', 'board-failure', 'water-leak', 'installation'],
  dishwasher: ['pump-failure', 'poor-washing', 'dishwasher-leak', 'heater-failure', 'door-lock-error', 'installation'],
  'display-fridge': ['not-cooling', 'compressor-failure', 'refrigerant-leak', 'thermostat-failure', 'installation'],
};

async function seed() {
  await sequelize.authenticate();
  await sequelize.sync();

  /* Admin */
  const hash = await bcrypt.hash('Admin@1234', 10);
  await User.findOrCreate({
    where: { email: 'admin@example.com' },
    defaults: { fullName: 'مدیر سامانه', email: 'admin@example.com', passwordHash: hash, role: 'admin' },
  });

  /* Brands */
  let i = 0;
  for (const [nameFa, nameEn, slug] of brands) {
    await Brand.findOrCreate({ where: { slug }, defaults: { nameFa, nameEn, slug, sortOrder: i++ } });
  }

  /* Appliance types */
  for (const [nameFa, slug, category, descriptionFa] of applianceTypes) {
    await ApplianceType.findOrCreate({ where: { slug }, defaults: { nameFa, slug, category, descriptionFa } });
  }

  /* Faults */
  for (const [nameFa, slug, descriptionFa, isCommon] of faults) {
    await FaultCategory.findOrCreate({ where: { slug }, defaults: { nameFa, slug, descriptionFa, isCommon } });
  }

  /* Junction appliance <-> fault */
  const appliances = await ApplianceType.findAll();
  const allFaults = await FaultCategory.findAll();
  for (const ap of appliances) {
    const slugs = faultMap[ap.slug] || [];
    const rows = allFaults.filter((f) => slugs.includes(f.slug));
    for (const f of rows) {
      await ApplianceTypeFault.findOrCreate({ where: { applianceTypeId: ap.id, faultCategoryId: f.id } });
    }
  }

  /* Geo */
  for (const [provName, cities] of Object.entries(geo)) {
    const provSlug = provName.replace(/\s/g, '-');
    const [province] = await Province.findOrCreate({ where: { slug: provSlug }, defaults: { nameFa: provName, slug: provSlug } });
    for (const cityName of cities) {
      await City.findOrCreate({
        where: { nameFa: cityName, provinceId: province.id },
        defaults: { nameFa: cityName, slug: cityName.replace(/\s/g, '-'), provinceId: province.id, hasCoverage: true },
      });
    }
  }

  /* Technicians */
  const tehran = await City.findOne({ where: { nameFa: 'تهران' } });
  for (const [fullName, phone, rating, specs] of technicians) {
    const exists = await Technician.findOne({ where: { phone } });
    if (!exists) await Technician.create({ fullName, phone, rating, specializations: specs, cityId: tehran?.id });
  }

  console.log('✅ Seeding completed');
  console.log('   Admin login → admin@example.com / Admin@1234');
  await sequelize.close();
}

seed().catch((e) => { console.error(e); process.exit(1); });
