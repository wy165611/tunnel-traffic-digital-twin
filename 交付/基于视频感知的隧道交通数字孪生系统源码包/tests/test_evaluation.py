import csv
import json
import pytest
from backend.evaluation import evaluate_run


@pytest.fixture
def sample_run(tmp_path):
    (tmp_path / 'run.json').write_text(json.dumps(dict(run_id='test-run', video_identity='video-hash')))
    def write(name, fields, rows):
        with (tmp_path / (name + '.csv')).open('w', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    write('traffic_statistics', ['timestamp', 'flow'], [dict(timestamp=t, flow=t) for t in range(4)])
    write('vehicles', ['timestamp', 'vehicle_id', 'speed', 'observed'], [
        dict(timestamp=1, vehicle_id=1, speed=40, observed=True),
        dict(timestamp=2, vehicle_id=1, speed=32, observed=True),
        dict(timestamp=3, vehicle_id=2, speed=70, observed=False),
        dict(timestamp=3, vehicle_id=3, speed='', observed=True)])
    write('events', ['timestamp', 'vehicle_id', 'event'], [
        dict(timestamp=1, vehicle_id=1, event='WRONG WAY'),
        dict(timestamp=1.05, vehicle_id=1, event='WRONG WAY'),
        dict(timestamp=2, vehicle_id=1, event='HARD BRAKING')])
    truth = dict(schema_version=1, verified=True, annotator='Synthetic unit fixture', video_identity='video-hash', interval=[0, 3],
                 crossings=[dict(timestamp=1), dict(timestamp=2)],
                 speeds=[dict(timestamp=1, vehicle_id=1, speed_kmh=36), dict(timestamp=2, vehicle_id=1, speed_kmh=36),
                         dict(timestamp=3, vehicle_id=2, speed_kmh=70), dict(timestamp=3, vehicle_id=3, speed_kmh=30)],
                 events=[dict(timestamp=1, vehicle_id=1, event='WRONG WAY'), dict(timestamp=2, vehicle_id=2, event='HARD BRAKING')])
    return tmp_path, truth


def test_eval_errors_coverage_and_one_to_one_events(sample_run):
    directory, truth = sample_run
    result = evaluate_run(directory, truth)
    assert result['flow'] == dict(predicted=3, truth=2, absolute_error=1)
    assert result['speed'] == dict(truth_samples=4, matched_samples=2, coverage=.5, mae_kmh=4, rmse_kmh=4)
    assert result['events']['true_positive'] == 1
    assert result['events']['false_positive'] == 2 and result['events']['false_negative'] == 1
    assert result['events']['precision'] == pytest.approx(1/3)


@pytest.mark.parametrize('change', [dict(verified=False), dict(video_identity='other'), dict(interval=[0, 4]),
                                    dict(interval=[0, float('nan')]), dict(annotator=''), dict(speeds=None)])
def test_eval_rejects_unverified_mismatched_or_incomplete_truth(sample_run, change):
    directory, truth = sample_run
    truth.update(change)
    with pytest.raises(ValueError):
        evaluate_run(directory, truth)


def test_missing_speed_and_empty_events_are_unavailable_not_perfect(sample_run):
    directory, truth = sample_run
    truth['speeds'] = [dict(timestamp=3, vehicle_id=3, speed_kmh=30)]
    truth['events'] = []
    result = evaluate_run(directory, truth)
    assert result['speed']['coverage'] == 0 and result['speed']['mae_kmh'] is None
    assert result['events']['recall'] is None
