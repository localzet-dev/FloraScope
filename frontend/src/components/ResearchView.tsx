import { Accordion } from "@mantine/core";
import {
  Database,
  EyeOff,
  GitBranch,
  Leaf,
  ScanLine,
  ShieldCheck,
  Waves,
} from "lucide-react";
export function ResearchView() {
  return (
    <section className="research-page">
      <div className="page-heading">
        <div>
          <h1>
            Метод и проверка<span className="heading-dot">.</span>
          </h1>
          <p>
            Как мы восстанавливаем данные и где заканчивается уверенность
            алгоритма.
          </p>
        </div>
      </div>
      <div className="method-hero">
        <div>
          <span className="eyebrow">ЭТАПЫ АНАЛИЗА</span>
          <h2>
            Что происходило
            <br />в пропусках?
            <br />
            <span>Что изменилось сейчас?</span>
          </h2>
          <p>
            FloraScope соединяет спутниковые наблюдения, восстанавливает
            временной ряд и сравнивает его с историей территории.
          </p>
        </div>
        <div className="method-flow">
          {[
            {
              icon: Database,
              n: "01",
              title: "Наблюдения",
              text: "Спутниковые измерения и контроль качества внутри контура.",
            },
            {
              icon: GitBranch,
              n: "02",
              title: "Восстановление",
              text: "Соседние даты, сезонность и вероятный спутниковый источник.",
            },
            {
              icon: Waves,
              n: "03",
              title: "Сравнение с историей",
              text: "Ожидание по другим годам, отклонение и его продолжительность.",
            },
            {
              icon: ScanLine,
              n: "04",
              title: "Событие и объяснение",
              text: "Наблюдения, спектральные и погодные признаки. Ограничения — рядом с результатом.",
            },
          ].map(({ icon: Icon, n, title, text }) => (
            <div className="method-step" key={n}>
              <span className="step-number">{n}</span>
              <Icon size={22} />
              <div>
                <b>{title}</b>
                <p>{text}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="principle-grid">
        <article className="card principle">
          <EyeOff size={25} />
          <span className="eyebrow">ВАЛИДАЦИЯ</span>
          <h3>Проверка на скрытых значениях</h3>
          <p>
            Мы временно скрываем известные значения и сравниваем предсказание с
            настоящим ответом. Динамические признаки этой же строки тоже
            исключаются, чтобы модель не подглядывала.
          </p>
        </article>
        <article className="card principle">
          <GitBranch size={25} />
          <span className="eyebrow">УЧЁТ ИСТОЧНИКА</span>
          <h3>У спутников разная роль.</h3>
          <p>
            В наблюдениях организаторов основной NDVI следует приоритету
            Sentinel-2 → Landsat → MODIS. Восстановление учитывает это правило,
            а идентификатор поля не используется для запоминания ответов.
          </p>
        </article>
        <article className="card principle">
          <Leaf size={25} />
          <span className="eyebrow">ОСТОРОЖНАЯ ИНТЕРПРЕТАЦИЯ</span>
          <h3>Отклонение — ещё не причина.</h3>
          <p>
            Снижение NDVI может быть связано с уборкой, сменой культуры, погодой
            или другими условиями. Поддержка данными не является вероятностью
            болезни или засухи.
          </p>
        </article>
      </div>
      <div className="method-reference card">
        <div>
          <span className="eyebrow">СПРАВКА</span>
          <h3>Термины</h3>
        </div>
        <Accordion variant="separated">
          <Accordion.Item value="ndvi">
            <Accordion.Control>Что такое NDVI?</Accordion.Control>
            <Accordion.Panel>
              Индекс отражения света растительностью, обычно от −1 до 1. У
              густой зелёной растительности он чаще выше, у голой почвы — ниже.
              Это не прямое измерение урожая.
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="restored">
            <Accordion.Control>
              Почему восстановление не совпадает с нормой?
            </Accordion.Control>
            <Accordion.Panel>
              Восстановление оценивает происходившее в конкретном сезоне. Норма
              описывает другие годы. Реальное изменение должно остаться
              заметным, а не исчезнуть при заполнении пропусков.
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="shift">
            <Accordion.Control>
              Что такое сдвиг сезонной фазы?
            </Accordion.Control>
            <Accordion.Panel>
              Вегетация может начаться или завершиться раньше обычного. Алгоритм
              сравнивает форму сезонных кривых при календарном сдвиге и без
              него. Это отдельный случай, который нельзя свести только к
              отрицательному отклонению.
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="rmse">
            <Accordion.Control>
              Чему можно доверять в проверке качества?
            </Accordion.Control>
            <Accordion.Panel>
              RMSE измеряет ошибку восстановления; меньше — лучше. Валидатор CSV
              проверяет формат и наличие нужных строк, но не точность
              предсказаний. CV оценивает временно скрытые известные значения;
              финальную оценку секретного теста дают организаторы.
            </Accordion.Panel>
          </Accordion.Item>
          <Accordion.Item value="limits">
            <Accordion.Control>Где находятся ограничения?</Accordion.Control>
            <Accordion.Panel>
              Недостаток истории мешает оценить норму. Облака уменьшают число
              наблюдений. Источники могут быть недоступны. Перенос на другую
              частоту спутника или другой тип ландшафта требует отдельной
              проверки. Интерфейс показывает отсутствие данных, а не заменяет
              его уверенным выводом.
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      </div>
      <div className="research-footnote">
        <ShieldCheck size={17} />
        <p>
          Подробные эксперименты, исходные результаты и команды воспроизведения
          сохранены в исследовательском отчёте репозитория.
        </p>
      </div>
    </section>
  );
}
