#!/bin/bash
# Copyright 2020 Google LLC.

set -euo pipefail


USAGE=$'
Example usage:
inference_deepvariant.sh --model_preset "WGS" --docker_build true --use_gpu true

Flags:
--docker_build (true|false)  Whether to build docker image. (default: false)
--dry_run (true|false)  If true, print out the main commands instead of running. (default: false)
--use_gpu (true|false)   Whether to use GPU when running case study. Make sure to specify vm_zone that is equipped with GPUs. (default: false)
--use_hp_information (true|false) Use to set --use_hp_information. Only set this for PACBIO.
--bin_version Version of DeepVariant model to use
--customized_model Path to checkpoint directory containing model checkpoint.
--regions Regions passed into both variant calling and hap.py.
--make_examples_extra_args Flags for make_examples, specified as "flag1=param1,flag2=param2".
--call_variants_extra_args Flags for call_variants, specified as "flag1=param1,flag2=param2".
--postprocess_variants_extra_args Flags for postprocess_variants, specified as "flag1=param1,flag2=param2".
--model_preset Preset case study to run: WGS, WES, PACBIO, or HYBRID_PACBIO_ILLUMINA.
--proposed_variants Path to VCF containing proposed variants. In make_examples_extra_args, you must also specify variant_caller=vcf_candidate_importer but not proposed_variants.

If model_preset is not specified, the below flags are required:
--model_type Type of DeepVariant model to run (WGS, WES, PACBIO, HYBRID_PACBIO_ILLUMINA)
--ref Path to GCP bucket containing ref file (.fa)
--bam Path to GCP bucket containing BAM
--truth_vcf Path to GCP bucket containing truth VCF
--truth_bed Path to GCP bucket containing truth BED
--capture_bed Path to GCP bucket containing captured file (only needed for WES model_type)

Note: All paths to dataset must be of the form "gs://..."
'

# Specify default values.
# Booleans; sorted alphabetically.
BUILD_DOCKER=false
DRY_RUN=false
USE_GPU=false
USE_HP_INFORMATION="unset"  # To distinguish whether this flag is set explicitly or not.
SAVE_INTERMEDIATE_RESULTS=false
# Strings; sorted alphabetically.
BAM=""
BIN_VERSION="1.1.0"
CALL_VARIANTS_ARGS=""
CAPTURE_BED=""
CUSTOMIZED_MODEL=""
MAKE_EXAMPLES_ARGS=""
MODEL_PRESET=""
MODEL_TYPE=""
POSTPROCESS_VARIANTS_ARGS=""
PROPOSED_VARIANTS=""
REF=""
REGIONS=""
TRUTH_BED=""
TRUTH_VCF=""

while (( "$#" )); do
  case "$1" in
    --docker_build)
      BUILD_DOCKER="$2"
      if [[ ${BUILD_DOCKER} != "true" ]] && [[ ${BUILD_DOCKER} != "false" ]]; then
        echo "Error: --docker_build needs to have value (true|false)." >&2
        echo "$USAGE" >&2
        exit 1
      fi
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --dry_run)
      DRY_RUN="$2"
      if [[ ${DRY_RUN} != "true" ]] && [[ ${DRY_RUN} != "false" ]]; then
        echo "Error: --dry_run needs to have value (true|false)." >&2
        echo "$USAGE" >&2
        exit 1
      fi
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --use_gpu)
      USE_GPU="$2"
      if [[ ${USE_GPU} != "true" ]] && [[ ${USE_GPU} != "false" ]]; then
        echo "Error: --use_gpu needs to have value (true|false)." >&2
        echo "$USAGE" >&2
        exit 1
      fi
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --use_hp_information)
      USE_HP_INFORMATION="$2"
      if [[ "${USE_HP_INFORMATION}" != "true" ]] && [[ "${USE_HP_INFORMATION}" != "false" ]]; then
        echo "Error: --use_hp_information needs to have value (true|false)." >&2
        echo "$USAGE" >&2
        exit 1
      fi
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --save_intermediate_results)
      SAVE_INTERMEDIATE_RESULTS="$2"
      if [[ "${SAVE_INTERMEDIATE_RESULTS}" != "true" ]] && [[ "${SAVE_INTERMEDIATE_RESULTS}" != "false" ]]; then
        echo "Error: --save_intermediate_results needs to have value (true|false)." >&2
        echo "$USAGE" >&2
        exit 1
      fi
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --regions)
      REGIONS="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --customized_model)
      CUSTOMIZED_MODEL="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --make_examples_extra_args)
      MAKE_EXAMPLES_ARGS="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --call_variants_extra_args)
      CALL_VARIANTS_ARGS="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --postprocess_variants_extra_args)
      POSTPROCESS_VARIANTS_ARGS="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --model_preset)
      MODEL_PRESET="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --model_type)
      MODEL_TYPE="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --bin_version)
      BIN_VERSION="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --ref)
      REF="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --bam)
      BAM="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --truth_vcf)
      TRUTH_VCF="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --truth_bed)
      TRUTH_BED="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --capture_bed)
      CAPTURE_BED="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --proposed_variants)
      PROPOSED_VARIANTS="$2"
      shift # Remove argument name from processing
      shift # Remove argument value from processing
      ;;
    --help)
      echo "$USAGE" >&2
      exit 1
      ;;
    -*|--*=) # other flags not supported
      echo "Error: unrecognized flag $1" >&2
      echo "Run with --help to see usage." >&2
      exit 1
      ;;
    *)
      echo "Error: unrecognized extra args $1" >&2
      echo "Run with --help to see usage." >&2
      exit 1
      ;;
  esac
done

## Presets
# These settings specify the commonly run case studies
GCS_DATA_DIR="https://storage.googleapis.com/deepvariant"
BASE="${HOME}/custom-case-study"

declare -a extra_args
declare -a happy_args
declare -a docker_args

if [[ "${MODEL_PRESET}" = "PACBIO" ]]; then
  MODEL_TYPE="PACBIO"
  BASE="${HOME}/pacbio-case-study"

  REF="${REF:=${GCS_DATA_DIR}/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna}"
  BAM="${BAM:=${GCS_DATA_DIR}/pacbio-case-study-testdata/HG003.pfda_challenge.grch38.phased.bam}"
  TRUTH_VCF="${TRUTH_VCF:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz}"
  TRUTH_BED="${TRUTH_BED:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed}"
elif [[ "${MODEL_PRESET}" = "WGS" ]]; then
  MODEL_TYPE="WGS"
  BASE="${HOME}/wgs-case-study"

  REF="${REF:=${GCS_DATA_DIR}/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna}"
  BAM="${BAM:=${GCS_DATA_DIR}/case-study-testdata/HG003.novaseq.pcr-free.35x.dedup.grch38_no_alt.bam}"
  TRUTH_VCF="${TRUTH_VCF:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz}"
  TRUTH_BED="${TRUTH_BED:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed}"
elif [[ "${MODEL_PRESET}" = "WES" ]]; then
  MODEL_TYPE="WES"
  BASE="${HOME}/wes-case-study"

  REF="${REF:=${GCS_DATA_DIR}/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna}"
  BAM="${BAM:=${GCS_DATA_DIR}/exome-case-study-testdata/HG003.novaseq.wes_idt.100x.dedup.bam}"
  TRUTH_VCF="${TRUTH_VCF:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz}"
  TRUTH_BED="${TRUTH_BED:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed}"
  CAPTURE_BED="${CAPTURE_BED:=${GCS_DATA_DIR}/exome-case-study-testdata/idt_capture_novogene.grch38.bed}"
elif [[ "${MODEL_PRESET}" = "HYBRID_PACBIO_ILLUMINA" ]]; then
  MODEL_TYPE="HYBRID_PACBIO_ILLUMINA"
  BASE="${HOME}/hybrid-pacbio-illumina-case-study"

  REF="${REF:=${GCS_DATA_DIR}/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna}"
  BAM="${BAM:=${GCS_DATA_DIR}/hybrid-case-study-testdata/HG003_hybrid_35x_ilmn_35x_pacb.grch38.phased.bam}"
  TRUTH_VCF="${TRUTH_VCF:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz}"
  TRUTH_BED="${TRUTH_BED:=${GCS_DATA_DIR}/case-study-testdata/HG003_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed}"
else
  if [[ -n "${MODEL_PRESET}" ]]; then
    echo "Error: --model_preset must be one of WGS, WES, PACBIO, HYBRID_PACBIO_ILLUMINA." >&2
    exit 1
  fi

fi

## Flag consistency sanity checks.

## The user should have not set --use_hp_information if it's not PACBIO.
if [[ "${USE_HP_INFORMATION}" != "unset" ]] && [[ "${MODEL_TYPE}" != "PACBIO" ]]; then
  echo "Error: Only set --use_hp_information for PACBIO." >&2
  exit 1
fi
if [[ "${USE_HP_INFORMATION}" == "unset" ]] && [[ "${MODEL_TYPE}" == "PACBIO" ]]; then
  # This is for backward-compatibility.
  echo "For PACBIO, set use_hp_information=true if it's not explicitly set."
  USE_HP_INFORMATION="true"
fi

N_SHARDS="64"
INPUT_DIR="${BASE}/input/data"
OUTPUT_DIR="${BASE}/output"
OUTPUT_VCF="deepvariant.output.vcf.gz"
OUTPUT_GVCF="deepvariant.output.g.vcf.gz"
LOG_DIR="${OUTPUT_DIR}/logs"

if [[ "${MODEL_TYPE}" = "WES" ]]; then
  if [[ -n "${REGIONS}" ]]; then
    echo "Error: --regions is not used with model_type WES. Please use --capture_bed." >&2
    exit 1
  fi
  extra_args+=( --regions "/input/$(basename $CAPTURE_BED)")
  happy_args+=( -T "${INPUT_DIR}/$(basename $CAPTURE_BED)")
fi

if [[ "${SAVE_INTERMEDIATE_RESULTS}" == "true" ]]; then
  extra_args+=( --intermediate_results_dir "/output/intermediate_results_dir")
fi

echo "========================="
echo "# Booleans; sorted alphabetically."
echo "BUILD_DOCKER: ${BUILD_DOCKER}"
echo "DRY_RUN: ${DRY_RUN}"
echo "USE_GPU: ${USE_GPU}"
echo "USE_HP_INFORMATION: ${USE_HP_INFORMATION}"
echo "SAVE_INTERMEDIATE_RESULTS: ${SAVE_INTERMEDIATE_RESULTS}"
echo "# Strings; sorted alphabetically."
echo "BAM: ${BAM}"
echo "BIN_VERSION: ${BIN_VERSION}"
echo "CALL_VARIANTS_ARGS: ${CALL_VARIANTS_ARGS}"
echo "CAPTURE_BED: ${CAPTURE_BED}"
echo "CUSTOMIZED_MODEL: ${CUSTOMIZED_MODEL}"
echo "MAKE_EXAMPLES_ARGS: ${MAKE_EXAMPLES_ARGS}"
echo "MODEL_PRESET: ${MODEL_PRESET}"
echo "MODEL_TYPE: ${MODEL_TYPE}"
echo "POSTPROCESS_VARIANTS_ARGS: ${POSTPROCESS_VARIANTS_ARGS}"
echo "PROPOSED_VARIANTS: ${PROPOSED_VARIANTS}"
echo "REF: ${REF}"
echo "REGIONS: ${REGIONS}"
echo "TRUTH_BED: ${TRUTH_BED}"
echo "TRUTH_VCF: ${TRUTH_VCF}"
echo "========================="

function run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    # Prints out command to stdout and a [DRY RUN] tag to stderr.
    # This allows the users to use the dry_run mode to get a list of
    # executable commands by redirecting stdout to a file.
    1>&2 printf "[DRY RUN] " && echo "$*"
  else
    echo "$*"
    eval "$@"
  fi
}

function copy_gs_or_http_file() {
  run echo "Copying from \"$1\" to \"$2\""
  if [[ "$1" == http* ]]; then
    run aria2c -c -x10 -s10 "$1" -d "$2"
  elif [[ "$1" == gs://* ]]; then
    run gsutil -m cp "$1" "$2"
  else
    echo "Unrecognized file format: $1" >&2
    exit 1
  fi
}

function copy_data() {
  copy_gs_or_http_file "${TRUTH_BED}" "${INPUT_DIR}"
  copy_gs_or_http_file "${TRUTH_VCF}" "${INPUT_DIR}"
  copy_gs_or_http_file "${TRUTH_VCF}.tbi" "${INPUT_DIR}"
  copy_gs_or_http_file "${BAM}" "${INPUT_DIR}"
  copy_gs_or_http_file "${BAM}.bai" "${INPUT_DIR}"
  copy_gs_or_http_file "${REF}.gz" "${INPUT_DIR}"
  copy_gs_or_http_file "${REF}.gz.fai" "${INPUT_DIR}"
  copy_gs_or_http_file "${REF}.gz.gzi" "${INPUT_DIR}"
  copy_gs_or_http_file "${REF}.gzi" "${INPUT_DIR}"
  copy_gs_or_http_file "${REF}.fai" "${INPUT_DIR}"
  if [[ "${MODEL_TYPE}" = "WES" ]]; then
    copy_gs_or_http_file "${CAPTURE_BED}" "${INPUT_DIR}"
  fi
  if [[ -n "${PROPOSED_VARIANTS}" ]]; then
    copy_gs_or_http_file "${PROPOSED_VARIANTS}" "${INPUT_DIR}"
    copy_gs_or_http_file "${PROPOSED_VARIANTS}.tbi" "${INPUT_DIR}"
  fi
}

function setup_test() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    return
  fi

  ## Create local directory structure
  mkdir -p "${OUTPUT_DIR}"
  mkdir -p "${INPUT_DIR}"
  mkdir -p "${LOG_DIR}"

  ## Download extra packages
  # Install aria2 to download data files.
  sudo apt-get -qq -y update
  sudo apt-get -qq -y install aria2

  if ! hash docker 2>/dev/null; then
    echo "'docker' was not found in PATH. Installing docker..."
    # Install docker using instructions on:
    # https://docs.docker.com/install/linux/docker-ce/ubuntu/
    sudo apt-get -qq -y install \
      apt-transport-https \
      ca-certificates \
      curl \
      gnupg-agent \
      software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository \
      "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) \
      stable"
    sudo apt-get -qq -y update
    sudo apt-get -qq -y install docker-ce
  fi
}

function get_docker_image() {
  if [[ "${BUILD_DOCKER}" = true ]]; then
    if [[ "${USE_GPU}" = true ]]; then
      IMAGE="deepvariant_gpu:latest"
      run "sudo docker build \
        --build-arg=FROM_IMAGE=nvidia/cuda:10.1-cudnn7-devel-ubuntu18.04 \
        --build-arg=DV_GPU_BUILD=1 -t deepvariant_gpu ."
      run echo "Done building GPU Docker image ${IMAGE}."
      docker_args+=( --gpus 1 )
    else
      IMAGE="deepvariant:latest"
      # Building twice in case the first one times out.
      run "sudo docker build -t deepvariant . --build-arg DV_OPENVINO_BUILD=1 || \
        (sleep 5 ; sudo docker build -t deepvariant . --build-arg DV_OPENVINO_BUILD=1)"
      run echo "Done building Docker image ${IMAGE}."
    fi

    # redacted
    # move to `docker run` command during the next release.
    extra_args+=( --runtime_report )
  else
    if [[ "${USE_GPU}" = true ]]; then
      IMAGE="google/deepvariant:${BIN_VERSION}-gpu"
      # shellcheck disable=SC2027
      # shellcheck disable=SC2086
      run "sudo docker pull "${IMAGE}" || \
        (sleep 5 ; sudo docker pull "${IMAGE}")"
      docker_args+=( --gpus 1 )
    else
      IMAGE="google/deepvariant:${BIN_VERSION}"
      # shellcheck disable=SC2027
      # shellcheck disable=SC2086
      run "sudo docker pull "${IMAGE}" || \
        (sleep 5 ; sudo docker pull "${IMAGE}")"
    fi
  fi
}

function setup_args() {
  if [[ -n "${CUSTOMIZED_MODEL}" ]]; then
    run echo "Copy from gs:// path ${CUSTOMIZED_MODEL} to ${INPUT_DIR}/"
    run gsutil cp "${CUSTOMIZED_MODEL}".data-00000-of-00001 "${INPUT_DIR}/model.ckpt.data-00000-of-00001"
    run gsutil cp "${CUSTOMIZED_MODEL}".index "${INPUT_DIR}/model.ckpt.index"
    run gsutil cp "${CUSTOMIZED_MODEL}".meta "${INPUT_DIR}/model.ckpt.meta"
    extra_args+=( --customized_model "/input/model.ckpt")
  else
    run echo "No custom model specified."
  fi
  if [[ -n "${MAKE_EXAMPLES_ARGS}" ]]; then
    # In order to use proposed variants, we have to pass vcf_candidate_importer
    # to make_examples_extra_args, so we know that we will enter this if
    # statement.
    if [[ -n "${PROPOSED_VARIANTS}" ]]; then
      MAKE_EXAMPLES_ARGS="${MAKE_EXAMPLES_ARGS},proposed_variants=/input/$(basename "$PROPOSED_VARIANTS")"
    fi
    extra_args+=( --make_examples_extra_args "${MAKE_EXAMPLES_ARGS}")
  fi
  if [[ -n "${CALL_VARIANTS_ARGS}" ]]; then
    extra_args+=( --call_variants_extra_args "${CALL_VARIANTS_ARGS}")
  fi
  if [[ "${USE_HP_INFORMATION}" == "true" ]] || [[ "${USE_HP_INFORMATION}" == "false" ]]; then
    # Note that because --use_hp_information is a binary flag, I need to use
    # the --flag=(true|false) format, or use --[no]flag format.
    extra_args+=( "--use_hp_information=${USE_HP_INFORMATION}" )
  fi
  if [[ -n "${POSTPROCESS_VARIANTS_ARGS}" ]]; then
    extra_args+=( --postprocess_variants_extra_args "${POSTPROCESS_VARIANTS_ARGS}")
  fi
  if [[ -n "${REGIONS}" ]]; then
    extra_args+=( --regions "${REGIONS}")
    happy_args+=( -l "${REGIONS}")
  fi
}

function run_deepvariant_with_docker() {
  run echo "Run DeepVariant..."
  run echo "using IMAGE=${IMAGE}"
  # shellcheck disable=SC2027
  # shellcheck disable=SC2046
  # shellcheck disable=SC2068
  # shellcheck disable=SC2086
  # shellcheck disable=SC2145
  run "(time (sudo docker run \
    -v "${INPUT_DIR}":"/input" \
    -v "${OUTPUT_DIR}:/output" \
    ${docker_args[@]-} \
    "${IMAGE}" \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type="${MODEL_TYPE}" \
    --ref="/input/$(basename $REF).gz" \
    --reads="/input/$(basename $BAM)" \
    --output_vcf="/output/${OUTPUT_VCF}" \
    --output_gvcf="/output/${OUTPUT_GVCF}" \
    --num_shards=${N_SHARDS} \
    --logging_dir="/output/logs" \
    "${extra_args[@]-}" && \
  echo "Done.")) 2>&1 | tee "${LOG_DIR}/deepvariant_runtime.log""
  echo
}


function run_happy() {
  ## Evaluation: run hap.py
  run echo "Start evaluation with hap.py..."
  UNCOMPRESSED_REF="${INPUT_DIR}/$(basename $REF)"
  # hap.py cannot read the compressed fa, so uncompress
  # into a writable directory. Index file was downloaded earlier.
  # shellcheck disable=SC2027
  # shellcheck disable=SC2046
  # shellcheck disable=SC2086
  run "zcat <"${INPUT_DIR}/$(basename $REF).gz" >"${UNCOMPRESSED_REF}""

  run "sudo docker pull jmcdani20/hap.py:v0.3.12"
  # shellcheck disable=SC2027
  # shellcheck disable=SC2046
  # shellcheck disable=SC2086
  # shellcheck disable=SC2145
  run "( sudo docker run -i \
  -v "${INPUT_DIR}:${INPUT_DIR}" \
  -v "${OUTPUT_DIR}:${OUTPUT_DIR}" \
  jmcdani20/hap.py:v0.3.12 /opt/hap.py/bin/hap.py \
    "${INPUT_DIR}/$(basename $TRUTH_VCF)" \
    "${OUTPUT_DIR}/${OUTPUT_VCF}" \
    -f "${INPUT_DIR}/$(basename $TRUTH_BED)" \
    -r "${UNCOMPRESSED_REF}" \
    -o "${OUTPUT_DIR}/happy.output" \
    --engine=vcfeval \
    --pass-only \
    ${happy_args[@]-} \
  ) 2>&1 | tee "${LOG_DIR}/happy.log""
  run echo "Done."
}

function main() {
  run echo 'Starting the test...'

  setup_test
  copy_data
  get_docker_image
  setup_args
  run_deepvariant_with_docker
  if [[ "${DRY_RUN}" == "true" ]]; then
    run_happy
  else
    run_happy 2>&1 | tee "${LOG_DIR}/happy.log"
  fi
}

main "$@"
