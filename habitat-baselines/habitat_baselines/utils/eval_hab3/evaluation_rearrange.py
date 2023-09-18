#!/usr/bin/env python3

# Copyright (c) Meta Platforms, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import glob
import json
import os
import pickle as pkl
import time
from multiprocessing import Pool
from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from tabulate import tabulate
from tqdm import tqdm

METRICS_INTEREST = [
    "composite_success",
    "num_steps",
    "num_steps_fail",
    "CR",
    "CRprop",
]
MAX_NUM_STEPS = 1500


# TODO: this should go into utilities
def pretty_print(metric_dict, latex=False, metric_names=None):
    def get_number_str(mean, std):
        if latex:
            return "${:0.2f}_{{ \\pm {:0.2f} }}$".format(mean, std)
        else:
            return "{:0.2f} \u00B1 {:0.2f}  ".format(mean, std)

    result_str = []
    if metric_names is None:
        metric_names = list(metric_dict)
    for metric_name in metric_names:
        mean, std = metric_dict[metric_name]
        number_str = get_number_str(mean, std)
        if not latex:
            curr_metric_str = f"{metric_name}: {number_str}"
        else:
            curr_metric_str = number_str

        result_str.append(curr_metric_str)

    if latex:
        return " & ".join(result_str)
    else:
        return " ".join(result_str)


def get_episode_info(file_name):
    # Read a single pickle file with results from an episode/seed
    # json_name = "/fsx-siro/xavierpuig/eval_data_akshara/" + file_name + ".json"
    # if os.path.isfile(json_name):
    #     with open(json_name, "r") as f:
    #         try:
    #             data = json.load(f)
    #             metrics = data["metrics"]
    #             id = data["id"]
    #         except:
    #             print(json_name)
    # if file type is pickle load it as pickle else load it as json
    solo = "solo" in file_name
    if file_name.endswith(".pkl"):
        if not solo:
            return None, None
        with open(file_name, "rb") as f:
            curr_result = pkl.load(f)
    else:
        with open(file_name, "r") as f:
            curr_result = json.load(f)

    metrics = {
        metric_name: curr_result["summary"][metric_name]
        for metric_name in METRICS_INTEREST
        if metric_name in curr_result["summary"]
    }
    id = curr_result["id"]
    if "num_steps_fail" in METRICS_INTEREST:
        if metrics["composite_success"] == 1:
            num_steps_fail = metrics["num_steps"]
        else:
            num_steps_fail = np.nan
        metrics["num_steps_fail"] = num_steps_fail
        metrics["num_steps_fail2"] = num_steps_fail

    if "num_agents_collide" in curr_result["summary"]:
        agent_collide = curr_result["summary"]["num_agents_collide"]
        metrics["CR"] = 1 if agent_collide > 0 else 0
        metrics["CRprop"] = agent_collide / curr_result["summary"]["num_steps"]
    # base_dir = os.path.dirname(json_name)

    # if not os.path.exists(base_dir):
    #     os.makedirs(base_dir)

    # with open(json_name, "w+") as f:
    #     dict_res = {"id": int(curr_result["id"]), "metrics": metrics}
    #     f.write(json.dumps(dict_res))
    return int(id), metrics


def aggregate_per_episode_dict(
    dict_data, average=False, std=False, solo_data=None, verbose=False
):
    # Given a dictionary where every episode has a list of metrics
    # Returns a dict with the metrics aggregated per episode

    # if num_steps_fail is nan, then set it as solo num_steps*1.5
    if verbose:
        breakpoint()
    if solo_data is not None:
        for episode_id, episode_data in dict_data.items():
            if episode_id in solo_data:
                for iter in range(len(episode_data)):
                    if np.isnan(episode_data[iter]["num_steps_fail"]):
                        episode_data[iter]["num_steps_fail2"] = np.min(
                            [
                                solo_data[episode_id]["num_steps"] * 1.5,
                                MAX_NUM_STEPS,
                            ]
                        )
                        episode_data[iter]["num_steps_fail"] = (
                            solo_data[episode_id]["num_steps"] * 1.5
                        )
                        # print("num_steps_fail is nan, composite success is", episode_data[iter]["composite_success"], " and solo success is ", solo_data[episode_id]["composite_success"])
                        # print("setting num_steps_fail to ", episode_data[iter]["num_steps_fail"], "solo num_steps is ", solo_data[episode_id]["num_steps"])
            else:
                print("Episode not found in solo data")
                continue

    new_dict_data = {}
    if verbose:
        breakpoint()
    for episode_id, episode_data in dict_data.items():
        if len(episode_data) == 0:
            breakpoint()
        metric_names = list(episode_data[0].keys())
        results_aggregation = {}
        for metric_name in metric_names:
            metric_list = np.array(
                [sample_data[metric_name] for sample_data in episode_data]
            )
            # remove nan values
            metric_list = metric_list[~np.isnan(metric_list)]
            if not average:
                result = metric_list
            else:
                if std:
                    result = (np.mean(metric_list), np.std(metric_list))
                else:
                    result = np.mean(metric_list)

            results_aggregation[metric_name] = result
        new_dict_data[episode_id] = results_aggregation
    return new_dict_data


def process_file(file_name):
    episode_id, episode_info = get_episode_info(file_name)
    return (episode_id, episode_info)


def get_dir_name(file_name):
    return os.path.dirname(
        # "/fsx-siro/xavierpuig/eval_data_akshara/" + file_name
        file_name
    )


def get_checkpoint_results(ckpt_path, separate_agent=False, solo_dict=None):
    # Reads files from folder ckpt_path
    # and averages different runs of the same episode
    t1 = time.time()
    if type(ckpt_path) is str:
        all_files = glob.glob(f"{ckpt_path}/*")
    else:
        all_files = []
        for ck_path in ckpt_path:
            all_files += sorted(glob.glob(f"{ck_path}/*"))
    dict_results: Dict[str, Any] = {}
    dict_results_agents: Dict[str, Dict[str, Any]] = {}
    episode_agents: Dict[str, Any] = {}

    # Create folders:
    # num_proc = 24
    # pool = Pool(num_proc)
    # res = pool.map(get_dir_name, all_files)
    # pool.close()
    # pool.join()
    # res = list(set(res))

    # for elem in res:
    #     if not os.path.exists(elem):
    #         os.makedirs(elem)

    num_proc = 24
    pool = Pool(num_proc)
    res = pool.map(process_file, all_files)
    pool.close()
    pool.join()
    res = [r for r in res if r[0] is not None]
    # res = []
    # for i in range(len(all_files)):
    #     res.append(process_file(all_files[i]))
    # num_threads = 24  # You can adjust this value based on your system's capabilities
    # with ThreadPoolExecutor(max_workers=num_threads) as executor:
    #     res = executor.map(process_file, all_files)

    for index, (episode_id, episode_info) in enumerate(res):
        if episode_id not in dict_results:
            dict_results[episode_id] = []

        dict_results[episode_id].append(episode_info)
        if separate_agent:
            agent_name = all_files[index].split("/")[-2]
            if agent_name not in episode_agents:
                episode_agents[agent_name] = {}
            if episode_id not in episode_agents[agent_name]:
                episode_agents[agent_name][episode_id] = []
            episode_agents[agent_name][episode_id].append(episode_info)

    # print(time.time() - t1)
    # Potentially verify here that no data is missing
    dict_results = aggregate_per_episode_dict(
        dict_results, average=True, std=False, solo_data=solo_dict
    )
    for agent_type in episode_agents.keys():
        dict_results_agents[agent_type] = aggregate_per_episode_dict(
            episode_agents[agent_type], average=True
        )
    # if separate_agent:
    #     breakpoint()
    return dict_results, dict_results_agents


def relative_metric(episode_baseline_data, episode_solo_data):
    try:
        assert episode_solo_data["composite_success"] == 1
    except:
        # print("Failed episode, solo success is ", episode_solo_data["composite_success"], " and baseline success is ", episode_baseline_data["composite_success"])
        # print("num steps of solo is ", episode_solo_data["num_steps"], " and baseline is ", episode_baseline_data["num_steps"])
        # episode_solo_data["num_steps"] = MAX_NUM_STEPS
        # episode_solo_data["num_steps_fail"] = MAX_NUM_STEPS
        return {}

    composite_success = episode_baseline_data["composite_success"]
    efficiency = (
        episode_solo_data["num_steps"] / episode_baseline_data["num_steps"]
    )
    RE = composite_success * efficiency * 100
    REMT = (
        episode_solo_data["num_steps"]
        / episode_baseline_data["num_steps_fail"]
    ) * 100
    REMT2 = (
        episode_solo_data["num_steps"]
        / episode_baseline_data["num_steps_fail2"]
    ) * 100
    if REMT2 < REMT:
        print(
            "REMT2 is ",
            REMT2,
            "REMT is ",
            REMT,
            "composite success is ",
            composite_success,
            "efficiency is ",
            efficiency,
        )
        print(
            "num steps fail is ",
            episode_baseline_data["num_steps_fail"],
            "num steps fail2 is ",
            episode_baseline_data["num_steps_fail2"],
        )
    # average efficiency when composite success is 1.0
    if composite_success == 1.0:
        RES = efficiency * 100
    else:
        RES = np.nan
    composite_success *= 100
    collision_rate = episode_baseline_data["CR"]

    collision_rate_proportion = episode_baseline_data["CRprop"]
    return {
        "composite_success": composite_success,
        "RE_MT2": REMT2,
        "CR": collision_rate,
        "CRprop": collision_rate_proportion,
    }


def compute_relative_metrics(per_episode_baseline_dict, per_episode_solo_dict):
    # Computes the aggregated metrics coming from a particular training checkpoint.
    res_dict = {}
    all_results = []
    for episode_id in per_episode_solo_dict:
        episode_solo_data = per_episode_solo_dict[episode_id]
        if episode_id not in per_episode_baseline_dict:
            # TODO: raise exception here
            continue
        episode_baseline_data = per_episode_baseline_dict[episode_id]
        curr_metric = relative_metric(episode_baseline_data, episode_solo_data)
        if len(curr_metric) == 0:
            # TODO: raise exception here
            continue
        all_results.append(curr_metric)
        res_dict[episode_id] = curr_metric

    if len(all_results) == 0:
        print(len(per_episode_baseline_dict))
        return {}
    average_over_episodes = aggregate_per_episode_dict(
        {"all_episodes": all_results}, average=True
    )
    return average_over_episodes["all_episodes"]


def compute_relative_metrics_multi_ckpt(
    experiments_path_dict, solo_path, latex=False, verbose=False
):
    # import ipdb; ipdb.set_trace()
    # Computes and prints metrics for all baselines
    # given the path of the solo episodes, and a dictionary baseline_name: path_res_baselines
    solo, _ = get_checkpoint_results(solo_path)
    res_zsc_list, res_per_seed_zsc_dict = {}, {}
    for baseline_name, baselines_path in experiments_path_dict.items():
        # print("baseline name ", baseline_name, " baseline path ", baselines_path)
        compiled_results_success = []
        compiled_results_efficiency = []
        compiled_results_CR = []
        results_across_seeds = {}

        all_results = []

        if verbose:
            print(f"Computing {baseline_name}...")
        for baseline_path in tqdm(baselines_path, disable=not verbose):
            all_results_zsc = {}
            if type(baselines_path) == list:
                baseline, _ = get_checkpoint_results(
                    baseline_path, separate_agent=True, solo_dict=solo
                )

            elif type(baselines_path) == dict:
                baseline, baseline_diff_zsc = get_checkpoint_results(
                    baselines_path[baseline_path],
                    separate_agent=True,
                    solo_dict=solo,
                )
            else:
                raise Exception

            curr_res = compute_relative_metrics(baseline, solo)
            all_results.append(curr_res)

            for agent_name in sorted(baseline_diff_zsc):
                curr_res = compute_relative_metrics(
                    baseline_diff_zsc[agent_name], solo
                )
                # breakpoint()
                if len(curr_res) > 0:
                    if agent_name not in all_results_zsc:
                        all_results_zsc[agent_name] = []
                    all_results_zsc[agent_name].append(curr_res)

            results_across_seeds[baseline_path] = all_results_zsc

        results_baseline = aggregate_per_episode_dict(
            {"all_episodes": all_results}, average=True, std=True
        )["all_episodes"]
        # ipdb.set_trace()

        metrics_str = pretty_print(results_baseline, latex=latex)
        print(f"{baseline_name}: {metrics_str}")
        results_baseline = {}
        cont = 0
        for baseline_path in sorted(results_across_seeds):
            all_results_zsc = results_across_seeds[baseline_path]
            res_dict_per_agent = {}
            for agent_name in all_results_zsc:
                all_res = all_results_zsc[agent_name]
                res_zsc = aggregate_per_episode_dict(
                    {"all_episodes": all_res}, average=True, std=True
                )["all_episodes"]
                compiled_results_success.append(
                    res_zsc["composite_success"][0]
                )
                compiled_results_efficiency.append(res_zsc["RE_MT2"][0])
                compiled_results_CR.append(res_zsc["CR"])

                metrics_str = pretty_print(res_zsc, latex=latex)

                print(f"{baseline_name}.{agent_name}: {metrics_str}")
                if agent_name not in results_baseline:
                    results_baseline[agent_name] = []

                # This holds the results per agent aggregated across seeds
                res_zsc_mean = {x: v[0] for x, v in res_zsc.items()}
                results_baseline[agent_name].append(res_zsc_mean)

                # This holds the results per agent per seed
                res_dict_per_agent[agent_name] = res_zsc_mean
            res_per_seed_zsc_dict[
                f"{baseline_name}.{cont}"
            ] = res_dict_per_agent
            cont += 1

        res_zsc = aggregate_per_episode_dict(
            results_baseline, average=True, std=True, verbose=False
        )
        # breakpoint()
        # print('-----')
        # avg_across_agents = {key: 0 for key in res_zsc.keys()}
        # for agent_name in all_results_zsc:
        #     # average composite success and other metrics per agent
        #     all_res = all_results_zsc[agent_name]
        #     res_zsc = aggregate_per_episode_dict(
        #         {"all_episodes": all_res}, average=True, std=True
        #     )["all_episodes"]
        #     for metric_name in res_zsc:
        #         avg_across_agents[metric_name] += res_zsc[metric_name][0]
        # for metric_name in avg_across_agents:
        #     avg_across_agents[metric_name] /= len(all_results_zsc)
        # for metric_name in avg_across_agents:
        #     avg_across_agents[metric_name] = (avg_across_agents[metric_name], 0.0)
        # metrics_str = pretty_print(avg_across_agents, latex=latex)
        # print(f"{baseline_name}.avg_across_agents: {metrics_str}")
        # print('-----')
        mean_success, std_success = np.mean(compiled_results_success), np.std(
            compiled_results_success
        )
        mean_efficiency, std_efficiency = np.mean(
            compiled_results_efficiency
        ), np.std(compiled_results_efficiency)
        mean_CR, std_CR = np.mean(compiled_results_CR), np.std(
            compiled_results_CR
        )
        print(
            f"{baseline_name}.compiled_results_success: {mean_success} \u00B1 {std_success}"
        )
        print(
            f"{baseline_name}.compiled_results_efficiency: {mean_efficiency} \u00B1 {std_efficiency}"
        )
        print(
            f"{baseline_name}.compiled_results_CR: {mean_CR} \u00B1 {std_CR}"
        )
        print("${:0.2f}_{{ \\pm {:0.2f} }}$".format(mean_CR, std_CR))
        res_zsc["Averaged"] = {
            "composite_success": (mean_success, std_success),
            "RE_MT2": (mean_efficiency, std_efficiency),
            "CR": (mean_CR, std_CR),
        }
        res_zsc_list[baseline_name] = res_zsc
        # breakpoint()
    return res_zsc_list, res_per_seed_zsc_dict


def compute_all_metrics(latex_print=False):
    root_dir = "/fsx-siro/akshararai/hab3/zsc_eval/20_ep_data"
    solo_path = f"{root_dir}/solo_eval_data"
    experiments_path = {
        "GT_coord": [
            f"{root_dir}/GTCoord_eval_data",
            f"{root_dir}/GTCoord_eval_data",
            f"{root_dir}/GTCoord_eval_data",
        ],
        "Pop_play": [
            f"{root_dir}/GTCoord_eval_data",
            f"{root_dir}/GTCoord_eval_data",
            f"{root_dir}/GTCoord_eval_data",
        ],
    }

    compute_relative_metrics_multi_ckpt(
        experiments_path, solo_path, latex=latex_print
    )


def extend_exps_zsc(dict_exps):
    # Increases the experiments to include info of different agents
    new_experiments_path = {}
    for exp_name, paths in dict_exps.items():
        paths_exp = []
        dict_paths = {}
        for path in paths:
            files = glob.glob(f"{path}/eval_data*")
            dict_paths[path] = files
        new_experiments_path[exp_name] = dict_paths
    return new_experiments_path


def compute_all_metrics_zsc(latex_print=False):
    # root_dir = "/fsx-siro/akshararai/hab3/zsc_eval/20_ep_data"
    root_dir = "/fsx-siro/akshararai/hab3/zsc_eval/zsc_eval_data/zsc_old_ckpt/zsc_eval_no_end/"
    root_dir_train_pop = "/fsx-siro/akshararai/hab3"
    root = "/fsx-siro/xavierpuig/multirun_latest"
    solo_path = (
        "/fsx-siro/akshararai/hab3/eval_solo/0/eval_data_multi_ep_speed_10"
    )
    experiments_path = {
        "Plan_play_-2": [
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/2",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/6",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/10",
        ],
        "Plan_play_-1": [
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/3",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/7",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/11",
        ],
        "Plan_play_-3": [
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/1",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/5",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/9",
        ],
        "Plan_play_-4": [
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/0",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/4",
            f"{root_dir}/speed_10/plan_play/2023-08-25/18-19-41/8",
        ],
        "GT_coord": [
            f"{root_dir}/speed_10/GTCoord/2023-08-19/00-07-24/0",
            f"{root_dir}/speed_10/GTCoord/2023-08-19/00-07-24/1",
            f"{root_dir}/speed_10/GTCoord/2023-08-19/00-07-24/2",
        ],
        "Pop_play": [
            f"{root_dir}/speed_10/pp8/2023-08-19/00-05-08/0",
            f"{root_dir}/speed_10/pp8/2023-08-19/00-05-08/1",
            f"{root_dir}/speed_10/pp8/2023-08-19/00-05-08/2",
        ],
        # "Plan_play_-1_train-pop": [
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/3/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/7/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/11/eval_no_end",
        # ],
        # "Plan_play_-2_train-pop": [
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/2/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/6/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/10/eval_no_end",
        # ],
        # "Plan_play_-3_train-pop": [
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/1/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/5/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/9/eval_no_end",
        # ],
        # "Plan_play_-4_train-pop": [
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/0/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/4/eval_no_end",
        #     f"{root_dir_train_pop}/plan_play/2023-08-25/18-19-41/8/eval_no_end",
        # ],
        # "GT_coord_train-pop": [
        #     f"{root_dir_train_pop}/GTCoord/2023-08-19/00-07-24/0/eval_no_end",
        #     f"{root_dir_train_pop}/GTCoord/2023-08-19/00-07-24/1/eval_no_end",
        #     f"{root_dir_train_pop}/GTCoord/2023-08-19/00-07-24/2/eval_no_end",
        # ],
        # "Pop_play_train-pop": [
        #     f"{root_dir_train_pop}/pp8/2023-08-19/00-05-08/0/eval_no_end",
        #     f"{root_dir_train_pop}/pp8/2023-08-19/00-05-08/1/eval_no_end",
        #     f"{root_dir_train_pop}/pp8/2023-08-19/00-05-08/2/eval_no_end",
        # ],
        # "Plan_play_-2": [
        # f"{root}/learned_skills_iclr/zsc_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/10",
        # f"{root}/learned_skills_iclr/zsc_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/2",
        # f"{root}/learned_skills_iclr/zsc_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/6",
        # ],
        # "Plan_play_-2_train-pop": [
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/10",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/2",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/plan_play/2023-08-25/18-19-41/6",
        # ],
        # "GTCoord-oracle-nav": [
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_oracle_nav/GTCoord/2023-08-19/00-07-24/0",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_oracle_nav/GTCoord/2023-08-19/00-07-24/1",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_oracle_nav/GTCoord/2023-08-19/00-07-24/2",
        # ],
        # "GTCoord_train-pop": [
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/GTCoord/2023-08-19/00-07-24/0",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/GTCoord/2023-08-19/00-07-24/1",
        # f"{root}/learned_skills_iclr/train_pop_learned_skill_learned_nav/GTCoord/2023-08-19/00-07-24/2",
        # ],
    }

    experiments_path = extend_exps_zsc(experiments_path)

    (
        results_agent_train_agent_type,
        results_train_agent_seed,
    ) = compute_relative_metrics_multi_ckpt(
        experiments_path, solo_path, latex=latex_print, verbose=True
    )

    with open("aggregated_results.pkl", "wb+") as f:
        pkl.dump([results_agent_train_agent_type, results_train_agent_seed], f)
    breakpoint()
    # print("-----")
    # experiments_path = extend_exps_zsc(experiments_path2)

    # compute_relative_metrics_multi_ckpt(
    #     experiments_path, solo_path, latex=latex_print
    # )


def str_func(dict_val, key_plot):
    mean, std = dict_val[key_plot]
    return "${:0.2f}_{{ \\pm {:0.2f} }}$".format(mean, std)


def convert_name(x):
    x = x.replace("eval_data_", "").replace(".pth", "")
    if "ckpt" in x:
        num = int(x.split(".")[-1])
        return "Learn-Single$_{{ {} }}$".format(num)
    elif "plan" in x:
        num = int(x.split("_")[-1][1:])
        num = 5 - num
        return "Plan$_{{ {} }}$".format(num)
    else:
        return x


def convert_name_method(x):
    x = x.replace("GT_coord", "Learn-Single")
    x = x.replace("Pop-Play", "Learn-Pop")
    if "Plan" in x:
        num = 5 - int(x[-1])
        x = "Plan-Pop$_{{ {} }}$".format(num)
    return x


def plot_per_agent_table(results_different_agents, key_plot="CR"):
    row_labels = list(results_different_agents.keys())
    column_labels = list(next(iter(results_different_agents.values())).keys())
    # row_labels = [convert_name(x) for x in row_labels]
    breakpoint()
    index_column = [0, 1, 2, 3, 4, 5, 9, 8, 7, 6, 10]
    column_labels = [column_labels[ind] for ind in index_column]
    values = [
        [
            results_different_agents[row][col][key_plot][0]
            for col in column_labels
        ]
        for row in row_labels
    ]
    annotations = [
        [
            str_func(results_different_agents[row][col], key_plot)
            for col in column_labels
        ]
        for row in row_labels
    ]

    sns.set()
    plt.figure(figsize=(15, 6))
    column_labels = [convert_name(x) for x in column_labels]
    row_labels = [convert_name_method(x) for x in row_labels]

    index_row = [4, 3, 2, 0, 1, 5]
    values = [values[ind] for ind in index_row]
    annotations = [annotations[ind] for ind in index_row]
    row_labels = [row_labels[ind] for ind in index_row]
    sns.heatmap(
        values,
        annot=annotations,
        fmt="",
        xticklabels=column_labels,
        yticklabels=row_labels,
        cmap="Blues",
        cbar=False,
    )
    # Set labels for the axes
    plt.xlabel("ZSC-Agents", fontsize=20)
    plt.ylabel("Training agents", fontsize=20)
    plt.xticks(fontsize=16, rotation=45)
    plt.yticks(fontsize=16)
    plt.axvline(x=10, ymin=0, ymax=9, color="white")

    # Save the plot to a PDF file
    plt.savefig("heatmap_zsc_success.pdf", format="pdf", bbox_inches="tight")


if __name__ == "__main__":
    print("\n\nResults")
    # compute_all_metrics(latex_print=False)
    # breakpoint()

    compute_all_metrics_zsc(latex_print=False)

    with open("aggregated_results.pkl", "rb") as f:
        cont = pkl.load(f)

    plot_per_agent_table(cont[0])
    breakpoint()
    print("\n\nLATEX")
    # compute_all_metrics(latex_print=True)
