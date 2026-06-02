import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import './style.css';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const LOSTARK_CLASSES = [
  '버서커', '디스트로이어', '워로드', '홀리나이트', '슬레이어',
  '배틀마스터', '인파이터', '기공사', '창술사', '스트라이커', '브레이커',
  '데빌헌터', '블래스터', '호크아이', '스카우터', '건슬링어',
  '바드', '서머너', '아르카나', '소서리스',
  '데모닉', '블레이드', '리퍼', '소울이터',
  '도화가', '기상술사',
];

const CLASS_ENGRAVINGS = {
  버서커: ['광전사의 비기', '광기'],
  디스트로이어: ['분노의 망치', '중력 수련'],
  워로드: ['고독한 기사', '전투 태세'],
  홀리나이트: ['축복의 오라', '심판자'],
  슬레이어: ['처단자', '포식자'],
  배틀마스터: ['초심', '오의 강화'],
  인파이터: ['극의: 체술', '충격 단련'],
  기공사: ['세맥타통', '역천지체'],
  창술사: ['절정', '절제'],
  스트라이커: ['오의난무', '일격필살'],
  브레이커: ['권왕파천무', '수라의 길'],
  데빌헌터: ['강화 무기', '핸드거너'],
  블래스터: ['포격 강화', '화력 강화'],
  호크아이: ['두 번째 동료', '죽음의 습격'],
  스카우터: ['진화의 유산', '아르데타인의 기술'],
  건슬링어: ['피스메이커', '사냥의 시간'],
  바드: ['절실한 구원', '진실된 용맹'],
  서머너: ['상급 소환사', '넘치는 교감'],
  아르카나: ['황후의 은총', '황제의 칙령'],
  소서리스: ['점화', '환류'],
  데모닉: ['멈출 수 없는 충동', '완벽한 억제'],
  블레이드: ['잔재된 기운', '버스트'],
  리퍼: ['달의 소리', '갈증'],
  소울이터: ['만월의 집행자', '그믐의 경계'],
  도화가: ['만개', '회귀'],
  기상술사: ['질풍노도', '이슬비'],
};

const SUPPORT_CLASSES = new Set(['바드', '도화가', '홀리나이트']);

const COMMON_STONE_ENGRAVINGS = [
  '원한', '예리한 둔기', '저주받은 인형', '아드레날린', '돌격대장', '타격의 대가',
  '질량 증가', '기습의 대가', '결투의 대가', '바리케이드', '슈퍼 차지', '속전속결',
  '안정된 상태', '정기 흡수', '각성', '전문의', '중갑 착용', '급소 타격', '마나의 흐름',
  '최대 마나 증가', '위기 모면', '구슬동자', '에테르 포식자',
];

const ACCESSORY_PARTS = [
  { name: '장신구 전체', code: 200000 },
  { name: '목걸이', code: 200010 },
  { name: '귀걸이', code: 200020 },
  { name: '반지', code: 200030 },
];

const STONE_CATEGORY_FALLBACKS = [
  { name: '자동/전체 검색', code: 0 },
  { name: '어빌리티 스톤', code: 300000 },
];

const GRADES = ['고대', '유물', '전설'];
const PRICE_MODES = [
  { value: 'min_buy_price', label: '최저 즉시구매가' },
  { value: 'avg_top_n', label: '상위 N개 평균가' },
];

const ACCESSORY_EFFECT_FALLBACKS = [
  '선택 안 함',
  '깨달음',
  '추가 피해',
  '공격력',
  '무기 공격력',
  '치명타 적중률',
  '치명타 피해',
  '적에게 주는 피해',
  '낙인력',
  '아군 강화',
];

function formatGold(value) {
  return `${Math.round(value).toLocaleString('ko-KR')} G`;
}

function formatKrw(value) {
  return `${Math.round(value).toLocaleString('ko-KR')} 원`;
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function toOptionsFromNames(names) {
  return names.map((name) => ({ name, code: name }));
}

function uniqueByName(items) {
  const seen = new Set();
  const result = [];
  for (const item of items || []) {
    if (!item?.name) continue;
    const key = `${item.name}:${item.code ?? ''}:${item.group_code ?? ''}:${item.group_name ?? ''}`;
    if (seen.has(key)) continue;
    result.push(item);
    seen.add(key);
  }
  return result;
}

function mergeOptions(primary, fallbackNames) {
  const fallback = toOptionsFromNames(fallbackNames);
  return uniqueByName([...(primary || []), ...fallback]);
}

function findOptionByName(options, name) {
  if (!name || name === '선택 안 함') return null;
  const normalized = String(name).trim();
  return (options || []).find((opt) => String(opt.name).trim() === normalized)
    || (options || []).find((opt) => String(opt.name).includes(normalized));
}

function normalizeCategories(parsedCategories, fallback) {
  const rows = [];
  for (const cat of parsedCategories || []) {
    rows.push({ name: cat.name, code: cat.code });
    for (const child of cat.children || []) {
      rows.push({ name: `${cat.name} > ${child.name}`, code: child.code });
    }
  }
  return uniqueByName([...rows, ...fallback]);
}

function flattenEtcOptions(parsed) {
  const result = [];
  for (const group of parsed?.etc_options || []) {
    const groupName = String(group.name || '');
    const groupCode = group.code;
    for (const child of group.children || []) {
      result.push({
        group_code: groupCode,
        group_name: groupName,
        code: child.code,
        name: child.name,
        label: `${groupName} / ${child.name}`,
      });
    }
  }
  return uniqueByName(result);
}

function accessoryEffectOptions(parsed) {
  const all = flattenEtcOptions(parsed);
  const filtered = all.filter((item) => {
    const text = `${item.group_name || ''} ${item.name || ''}`;
    if (text.includes('각인')) return false;
    if (['치명', '특화', '신속', '제압', '인내', '숙련'].includes(item.name)) return false;
    return (
      text.includes('연마') ||
      text.includes('장신구') ||
      text.includes('깨달음') ||
      text.includes('아크') ||
      text.includes('공격') ||
      text.includes('피해') ||
      text.includes('낙인') ||
      text.includes('치명타') ||
      text.includes('아군')
    );
  });
  return mergeOptions(filtered, ACCESSORY_EFFECT_FALLBACKS);
}

function makeEtcOptionFromList(options, optionName, minValue = 1, maxValue = 999999) {
  const found = findOptionByName(options, optionName);
  if (!found || found.group_code == null || found.code == null) return null;
  return {
    FirstOption: Number(found.group_code),
    SecondOption: Number(found.code),
    MinValue: Number(minValue),
    MaxValue: Number(maxValue),
  };
}

function makeStoneEngravingOption(parsed, optionName) {
  return makeEtcOptionFromList(parsed?.engraving_options || [], optionName, 1, 999999);
}

function makeAccessoryEffectOption(parsed, optionName, minValue) {
  return makeEtcOptionFromList(accessoryEffectOptions(parsed), optionName, minValue, 999999);
}

function StatCard({ title, value, sub }) {
  return (
    <div className="stat-card">
      <p className="stat-title">{title}</p>
      <h3>{value}</h3>
      {sub ? <p className="stat-sub">{sub}</p> : null}
    </div>
  );
}

function SelectField({ label, value, onChange, children, disabled = false }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        {children}
      </select>
    </label>
  );
}

function NumberField({ label, value, onChange, min, max, step = 1, placeholder }) {
  return (
    <label>
      {label}
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function AuctionSearchPanel({ onSaved }) {
  const [mode, setMode] = useState('accessory');
  const [parsedOptions, setParsedOptions] = useState(null);
  const [rawPath, setRawPath] = useState('');
  const [auctionResult, setAuctionResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    key: 'accessory_base',
    name: '장신구 세팅비',
    price_mode: 'min_buy_price',
    save_as_latest: true,
    top_n: 10,
    item_tier: 4,
    item_grade: '고대',
    class_name: '소서리스',
    class_engraving: '점화',
    preset_role: '딜러',
    accessory_part_code: 200000,
    stone_category_code: 0,
    quality_min: 80,
    polish_stage: 3,
    enlightenment_min: 0,
    accessory_effect1: '선택 안 함',
    accessory_effect1_min: 0,
    accessory_effect2: '선택 안 함',
    accessory_effect2_min: 0,
    stone_engraving1: '원한',
    stone_engraving2: '예리한 둔기',
    item_name: '',
    page_no: 1,
  });

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const classOptions = useMemo(() => mergeOptions(parsedOptions?.classes, LOSTARK_CLASSES), [parsedOptions]);

  const classEngravings = useMemo(() => {
    return mergeOptions([], CLASS_ENGRAVINGS[form.class_name] || []);
  }, [form.class_name]);

  const stoneEngravingOptions = useMemo(() => {
    return mergeOptions(parsedOptions?.engraving_options, COMMON_STONE_ENGRAVINGS);
  }, [parsedOptions]);

  const gradeOptions = useMemo(() => mergeOptions(parsedOptions?.grades, GRADES), [parsedOptions]);

  const accessoryCategories = useMemo(() => {
    return normalizeCategories(parsedOptions?.categories, ACCESSORY_PARTS);
  }, [parsedOptions]);

  const stoneCategories = useMemo(() => {
    const fromApi = (parsedOptions?.categories || []).filter((x) => String(x.name || '').includes('스톤'));
    return normalizeCategories(fromApi, STONE_CATEGORY_FALLBACKS);
  }, [parsedOptions]);

  const accessoryOptions = useMemo(() => accessoryEffectOptions(parsedOptions), [parsedOptions]);

  const switchMode = (nextMode) => {
    setMode(nextMode);
    if (nextMode === 'accessory') {
      setForm((prev) => ({ ...prev, key: 'accessory_base', name: `${prev.class_name} ${prev.class_engraving} 장신구 세팅비`, item_name: '' }));
    } else {
      setForm((prev) => ({ ...prev, key: 'ability_stone', name: '어빌리티 스톤 가격', item_name: '어빌리티 스톤' }));
    }
  };

  const applyPreset = () => {
    const role = SUPPORT_CLASSES.has(form.class_name) ? '서포터' : '딜러';
    setForm((prev) => ({
      ...prev,
      preset_role: role,
      name: `${prev.class_name} ${prev.class_engraving} 장신구 세팅비`,
      key: 'accessory_base',
      item_tier: 4,
      item_grade: '고대',
      quality_min: role === '서포터' ? 80 : 85,
      polish_stage: 3,
      accessory_effect1: '선택 안 함',
      accessory_effect1_min: 0,
      accessory_effect2: '선택 안 함',
      accessory_effect2_min: 0,
    }));
  };

  const loadOptions = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${API_BASE}/api/options/auctions/parsed`);
      setParsedOptions(res.data.parsed);
      setRawPath(res.data.raw_path);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || '경매장 옵션 조회 실패');
    } finally {
      setLoading(false);
    }
  };

  const payload = useMemo(() => {
    const etcOptions = [];
    const missing = [];

    const addAccessoryOption = (name, min) => {
      if (!name || name === '선택 안 함') return;
      const option = makeAccessoryEffectOption(parsedOptions, name, min);
      if (option) etcOptions.push(option);
      else if (parsedOptions) missing.push(name);
    };

    const addStoneEngraving = (name) => {
      if (!name || name === '선택 안 함') return;
      const option = makeStoneEngravingOption(parsedOptions, name);
      if (option) etcOptions.push(option);
      else if (parsedOptions) missing.push(name);
    };

    if (mode === 'accessory') {
      addAccessoryOption(form.accessory_effect1, form.accessory_effect1_min);
      addAccessoryOption(form.accessory_effect2, form.accessory_effect2_min);
      if (Number(form.enlightenment_min) > 0) {
        addAccessoryOption('깨달음', form.enlightenment_min);
      }
    } else {
      addStoneEngraving(form.stone_engraving1);
      addStoneEngraving(form.stone_engraving2);
    }

    const built = {
      CategoryCode: Number(mode === 'accessory' ? form.accessory_part_code : form.stone_category_code),
      ItemTier: Number(form.item_tier),
      ItemGrade: form.item_grade || undefined,
      ItemGradeQuality: mode === 'accessory' ? Number(form.quality_min) : undefined,
      PageNo: Number(form.page_no),
      Sort: 'BUY_PRICE',
      SortCondition: 'ASC',
      ItemName: mode === 'stone' ? (form.item_name || '어빌리티 스톤') : form.item_name,
      SkillOptions: [],
      EtcOptions: etcOptions,
    };

    Object.keys(built).forEach((key) => {
      if (built[key] === undefined || built[key] === '') delete built[key];
    });
    return { built, missing };
  }, [form, mode, parsedOptions]);

  const searchAuction = async () => {
    setLoading(true);
    setError('');
    setAuctionResult(null);
    try {
      const res = await axios.post(`${API_BASE}/api/auctions/search`, {
        key: form.key,
        name: form.name,
        payload: payload.built,
        price_mode: form.price_mode,
        save_as_latest: form.save_as_latest,
        top_n: Number(form.top_n),
      });
      setAuctionResult(res.data);
      if (res.data.saved_to && onSaved) onSaved();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const hint = e?.response?.data?.hint;
      setError(`${detail || e.message || '경매장 검색 실패'}${hint ? `\n${hint}` : ''}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="section-title-row">
        <div>
          <h2>장신구/스톤 경매장 검색</h2>
          <p className="muted">
            현재 장신구 기준에 맞춰 악세 검색에서 특성과 유효각인을 제거했습니다. 직업과 직업각인은 검색 조건이 아니라
            프리셋 추천과 결과 이름에만 사용합니다. 실제 검색 조건은 부위, 등급, 품질, 연마/깨달음 옵션 중심입니다.
          </p>
        </div>
        <button className="secondary" onClick={loadOptions} disabled={loading}>
          {parsedOptions ? '옵션 다시 조회' : '경매장 옵션 조회'}
        </button>
      </div>

      <div className="mode-tabs">
        <button className={mode === 'accessory' ? 'tab active' : 'tab'} onClick={() => switchMode('accessory')}>장신구</button>
        <button className={mode === 'stone' ? 'tab active' : 'tab'} onClick={() => switchMode('stone')}>어빌리티 스톤</button>
      </div>

      {!parsedOptions ? (
        <div className="warning-box">
          먼저 <strong>경매장 옵션 조회</strong>를 눌러주세요. 조회 후 장신구 연마/깨달음 옵션과 스톤 각인 코드가 자동으로 매칭됩니다.
          API 키가 없으면 기본 드롭다운은 보이지만 세부 옵션 코드는 payload에 들어가지 않을 수 있습니다.
        </div>
      ) : rawPath ? <p className="source-note">옵션 원본 저장: {rawPath}</p> : null}

      <div className="form-grid auction-grid compact-grid">
        <SelectField label="검색 유형" value={mode} onChange={switchMode}>
          <option value="accessory">장신구</option>
          <option value="stone">어빌리티 스톤</option>
        </SelectField>
        <label>
          저장 키
          <input value={form.key} onChange={(e) => update('key', e.target.value)} />
        </label>
        <label>
          표시 이름
          <input value={form.name} onChange={(e) => update('name', e.target.value)} />
        </label>
        <SelectField label="가격 계산 방식" value={form.price_mode} onChange={(v) => update('price_mode', v)}>
          {PRICE_MODES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </SelectField>
      </div>

      <div className="builder-card">
        <h3>1. 직업/직각 프리셋</h3>
        <p className="muted small-muted">
          이 값은 장신구 경매장 payload에 직접 들어가지 않습니다. 현재 장신구에는 특성/유효각인 검색을 쓰지 않고,
          직업별 기본 품질·역할 프리셋과 결과 이름을 정하는 데만 사용합니다.
        </p>
        <div className="form-grid auction-grid compact-grid">
          <SelectField label="직업" value={form.class_name} onChange={(v) => {
            const next = CLASS_ENGRAVINGS[v]?.[0] || '선택 안 함';
            setForm((prev) => ({
              ...prev,
              class_name: v,
              class_engraving: next,
              preset_role: SUPPORT_CLASSES.has(v) ? '서포터' : '딜러',
            }));
          }}>
            {classOptions.map((item) => <option key={`${item.name}-${item.code}`} value={item.name}>{item.name}</option>)}
          </SelectField>
          <SelectField label="직업 각인" value={form.class_engraving} onChange={(v) => update('class_engraving', v)}>
            <option value="선택 안 함">선택 안 함</option>
            {classEngravings.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
          </SelectField>
          <SelectField label="세팅 역할" value={form.preset_role} onChange={(v) => update('preset_role', v)}>
            <option value="딜러">딜러</option>
            <option value="서포터">서포터</option>
            <option value="커스텀">커스텀</option>
          </SelectField>
          <label className="button-label">
            프리셋 적용
            <button type="button" className="ghost full-button" onClick={applyPreset}>직업 기준 자동 설정</button>
          </label>
        </div>
      </div>

      <div className="builder-card">
        <h3>2. {mode === 'accessory' ? '장신구 검색 조건' : '어빌리티 스톤 검색 조건'}</h3>
        <div className="form-grid auction-grid compact-grid">
          {mode === 'accessory' ? (
            <>
              <SelectField label="장신구 부위" value={form.accessory_part_code} onChange={(v) => update('accessory_part_code', v)}>
                {accessoryCategories.map((item) => <option key={`${item.name}-${item.code}`} value={item.code}>{item.name} ({item.code})</option>)}
              </SelectField>
              <SelectField label="등급" value={form.item_grade} onChange={(v) => update('item_grade', v)}>
                {gradeOptions.map((item) => <option key={`${item.name}-${item.code}`} value={item.name}>{item.name}</option>)}
              </SelectField>
              <NumberField label="티어" value={form.item_tier} onChange={(v) => update('item_tier', v)} min="1" max="4" />
              <NumberField label="최소 품질" value={form.quality_min} onChange={(v) => update('quality_min', v)} min="0" max="100" />
              <NumberField label="연마 단계" value={form.polish_stage} onChange={(v) => update('polish_stage', v)} min="0" max="3" />
              <NumberField label="깨달음 최소값" value={form.enlightenment_min} onChange={(v) => update('enlightenment_min', v)} min="0" placeholder="선택 입력" />
              <SelectField label="연마/아크 옵션 1" value={form.accessory_effect1} onChange={(v) => update('accessory_effect1', v)}>
                {accessoryOptions.map((item) => <option key={`${item.name}-${item.code}-${item.group_code}-a1`} value={item.name}>{item.label || item.name}</option>)}
              </SelectField>
              <NumberField label="옵션 1 최소값" value={form.accessory_effect1_min} onChange={(v) => update('accessory_effect1_min', v)} min="0" />
              <SelectField label="연마/아크 옵션 2" value={form.accessory_effect2} onChange={(v) => update('accessory_effect2', v)}>
                {accessoryOptions.map((item) => <option key={`${item.name}-${item.code}-${item.group_code}-a2`} value={item.name}>{item.label || item.name}</option>)}
              </SelectField>
              <NumberField label="옵션 2 최소값" value={form.accessory_effect2_min} onChange={(v) => update('accessory_effect2_min', v)} min="0" />
            </>
          ) : (
            <>
              <SelectField label="스톤 카테고리" value={form.stone_category_code} onChange={(v) => update('stone_category_code', v)}>
                {stoneCategories.map((item) => <option key={`${item.name}-${item.code}`} value={item.code}>{item.name} ({item.code})</option>)}
              </SelectField>
              <label>
                아이템명
                <input value={form.item_name} onChange={(e) => update('item_name', e.target.value)} placeholder="예: 어빌리티 스톤" />
              </label>
              <SelectField label="등급" value={form.item_grade} onChange={(v) => update('item_grade', v)}>
                {gradeOptions.map((item) => <option key={`${item.name}-${item.code}`} value={item.name}>{item.name}</option>)}
              </SelectField>
              <NumberField label="티어" value={form.item_tier} onChange={(v) => update('item_tier', v)} min="1" max="4" />
              <SelectField label="스톤 각인 1" value={form.stone_engraving1} onChange={(v) => update('stone_engraving1', v)}>
                <option value="선택 안 함">선택 안 함</option>
                {stoneEngravingOptions.map((item) => <option key={`${item.name}-${item.code}-se1`} value={item.name}>{item.name}</option>)}
              </SelectField>
              <SelectField label="스톤 각인 2" value={form.stone_engraving2} onChange={(v) => update('stone_engraving2', v)}>
                <option value="선택 안 함">선택 안 함</option>
                {stoneEngravingOptions.map((item) => <option key={`${item.name}-${item.code}-se2`} value={item.name}>{item.name}</option>)}
              </SelectField>
            </>
          )}
          <NumberField label="표시 매물 수" value={form.top_n} onChange={(v) => update('top_n', v)} min="1" max="50" />
        </div>
      </div>

      {payload.missing.length ? (
        <div className="warning-box danger">
          옵션 코드 자동 매칭 실패: {payload.missing.join(', ')}. 경매장 옵션 조회 결과에 해당 이름이 있는지 확인하거나 조건을 줄여서 검색하세요.
        </div>
      ) : null}

      <div className="checks">
        <label>
          <input type="checkbox" checked={form.save_as_latest} onChange={(e) => update('save_as_latest', e.target.checked)} />
          검색 가격을 latest_prices.json에 저장
        </label>
      </div>

      <details className="json-box payload-preview">
        <summary>자동 생성된 API payload 보기</summary>
        <pre>{prettyJson(payload.built)}</pre>
      </details>

      <button className="primary" onClick={searchAuction} disabled={loading}>
        {loading ? '조회 중...' : '경매장 검색/가격 저장'}
      </button>
      {error ? <p className="error whitespace">{error}</p> : null}

      {auctionResult ? (
        <div className="auction-result">
          <h3>검색 결과</h3>
          <p className="source-note">
            추정 가격: {auctionResult.price_gold ? formatGold(auctionResult.price_gold) : '가격 없음'} · 총 검색 수: {auctionResult.total_count ?? '알 수 없음'} · 원본: {auctionResult.raw_path}
          </p>
          {auctionResult.saved_to ? <p className="saved-note">latest_prices.json에 저장됨: {auctionResult.saved_to}</p> : null}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>이름</th>
                  <th>등급</th>
                  <th>품질</th>
                  <th>즉구가</th>
                  <th>입찰가</th>
                  <th>옵션 요약</th>
                </tr>
              </thead>
              <tbody>
                {auctionResult.items.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.item_name || '-'}</td>
                    <td>{item.grade || '-'}</td>
                    <td>{item.quality ?? '-'}</td>
                    <td>{item.buy_price ? formatGold(item.buy_price) : '-'}</td>
                    <td>{item.bid_price ? formatGold(item.bid_price) : '-'}</td>
                    <td>{item.options?.join(', ') || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function LatestPricesPanel({ refreshKey }) {
  const [prices, setPrices] = useState(null);
  const [error, setError] = useState('');

  React.useEffect(() => {
    let ignore = false;
    axios.get(`${API_BASE}/api/prices/latest`)
      .then((res) => { if (!ignore) setPrices(res.data); })
      .catch((e) => { if (!ignore) setError(e.message); });
    return () => { ignore = true; };
  }, [refreshKey]);

  const rows = useMemo(() => Object.values(prices?.prices || {}), [prices]);
  if (error) return <p className="error">가격 조회 실패: {error}</p>;
  return (
    <section className="panel compact-panel">
      <h2>현재 저장된 가격</h2>
      <p className="source-note">updated_at: {prices?.updated_at || '없음'}</p>
      {rows.length === 0 ? <p className="muted">아직 저장된 가격이 없습니다.</p> : (
        <div className="price-list">
          {rows.map((row) => (
            <div className="price-chip" key={row.key}>
              <span>{row.name || row.key}</span>
              <strong>{row.price_gold ? formatGold(row.price_gold) : '가격 없음'}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function App() {
  const [form, setForm] = useState({
    users: 1000,
    seed: 42,
    krw_per_gold: 0.4,
    include_stone: true,
    include_accessory: true,
    stone_target_a: 7,
    stone_target_b: 7,
    stone_max_negative: 4,
    stone_price_gold: '',
    accessory_base_gold: '',
    use_latest_api_prices: true,
    actual_user_gold: '',
    save_parquet: false,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const runSimulation = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const requestPayload = {
        ...form,
        users: Number(form.users),
        seed: Number(form.seed),
        krw_per_gold: Number(form.krw_per_gold),
        stone_target_a: Number(form.stone_target_a),
        stone_target_b: Number(form.stone_target_b),
        stone_max_negative: Number(form.stone_max_negative),
        stone_price_gold: form.stone_price_gold === '' ? null : Number(form.stone_price_gold),
        accessory_base_gold: form.accessory_base_gold === '' ? null : Number(form.accessory_base_gold),
        actual_user_gold: form.actual_user_gold === '' ? null : Number(form.actual_user_gold),
      };
      const res = await axios.post(`${API_BASE}/api/simulations/run`, requestPayload);
      setResult(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || '시뮬레이션 실패');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">LOA-HSI</p>
          <h1>나는 정말 접을 만큼 운이 없었을까?</h1>
          <p className="lead">
            재련, 어빌리티 스톤, 장신구 세팅 비용을 Monte Carlo 방식으로 시뮬레이션하고
            평균 비용이 아닌 P90/P99 체감 불운 비용을 계산합니다.
          </p>
        </div>
      </section>

      <AuctionSearchPanel onSaved={() => setRefreshKey((x) => x + 1)} />
      <LatestPricesPanel refreshKey={refreshKey} />

      <section className="panel grid-two">
        <div>
          <h2>시뮬레이션 설정</h2>
          <div className="form-grid">
            <NumberField label="유저 수" value={form.users} onChange={(v) => update('users', v)} />
            <NumberField label="랜덤 시드" value={form.seed} onChange={(v) => update('seed', v)} />
            <NumberField label="1골드 원화 환산" value={form.krw_per_gold} onChange={(v) => update('krw_per_gold', v)} step="0.01" />
            <NumberField label="내가 쓴 총 골드" value={form.actual_user_gold} onChange={(v) => update('actual_user_gold', v)} placeholder="선택 입력" />
            <NumberField label="목표 스톤 A" value={form.stone_target_a} onChange={(v) => update('stone_target_a', v)} />
            <NumberField label="목표 스톤 B" value={form.stone_target_b} onChange={(v) => update('stone_target_b', v)} />
            <NumberField label="스톤 1개 가격" value={form.stone_price_gold} onChange={(v) => update('stone_price_gold', v)} placeholder="비우면 API latest: ability_stone" />
            <NumberField label="장신구 기본 세팅비" value={form.accessory_base_gold} onChange={(v) => update('accessory_base_gold', v)} placeholder="비우면 API latest: accessory_base" />
          </div>

          <div className="checks">
            <label>
              <input type="checkbox" checked={form.include_stone} onChange={(e) => update('include_stone', e.target.checked)} />
              어빌리티 스톤 포함
            </label>
            <label>
              <input type="checkbox" checked={form.include_accessory} onChange={(e) => update('include_accessory', e.target.checked)} />
              장신구 포함
            </label>
            <label>
              <input type="checkbox" checked={form.use_latest_api_prices} onChange={(e) => update('use_latest_api_prices', e.target.checked)} />
              API 최신 수집 가격 사용
            </label>
            <label>
              <input type="checkbox" checked={form.save_parquet} onChange={(e) => update('save_parquet', e.target.checked)} />
              결과 Parquet 저장
            </label>
          </div>

          <button className="primary" onClick={runSimulation} disabled={loading}>
            {loading ? '계산 중...' : '시뮬레이션 실행'}
          </button>
          {error ? <p className="error">{error}</p> : null}
        </div>

        <div className="story-card">
          <h2>발표 서사</h2>
          <p>
            게임을 하다가 캐릭터 성장 운이 너무 나빠서 남들보다 비용을 많이 썼고,
            그 현타로 게임을 접었습니다. 이 프로젝트는 그 선택이 단순한 기분 탓이었는지,
            아니면 실제로 확률적으로 불운한 구간이었는지 검증합니다.
          </p>
        </div>
      </section>

      {result ? (
        <section className="panel">
          <h2>결과 요약</h2>
          <p className="source-note">가격 출처: {result.price_source === 'latest_api_prices' ? 'API 최신 수집 가격' : '샘플 가격'}</p>
          <div className="stats">
            <StatCard title="평균 비용" value={formatGold(result.avg_gold)} sub={formatKrw(result.avg_krw)} />
            <StatCard title="P90 불운 비용" value={formatGold(result.p90_gold)} sub={formatKrw(result.p90_krw)} />
            <StatCard title="P99 극단 불운 비용" value={formatGold(result.p99_gold)} sub={formatKrw(result.p99_krw)} />
            <StatCard title="현금 불운세" value={formatGold(result.bad_luck_tax_gold)} sub={formatKrw(result.bad_luck_tax_krw)} />
          </div>

          {result.user_message ? <div className="verdict">{result.user_message}</div> : null}

          <div className="chart-wrap">
            <h3>총비용 분포</h3>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={result.histogram}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" angle={-20} textAnchor="end" height={80} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="breakdown">
            <h3>평균 비용 구성</h3>
            <ul>
              <li>재련 평균: {formatGold(result.honing_avg_gold)}</li>
              <li>스톤 평균: {formatGold(result.stone_avg_gold)}</li>
              <li>장신구 평균: {formatGold(result.accessory_avg_gold)}</li>
              <li>평균 최장 연속 실패: {result.max_fail_streak_avg.toFixed(1)}회</li>
              <li>평균 스톤 구매 횟수: {result.stone_attempts_avg.toFixed(1)}개</li>
            </ul>
            {result.parquet_path ? <p>저장 경로: {result.parquet_path}</p> : null}
          </div>

          <details className="assumptions">
            <summary>현재 모델 가정 보기</summary>
            <ul>
              {result.assumptions.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </details>
        </section>
      ) : null}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
