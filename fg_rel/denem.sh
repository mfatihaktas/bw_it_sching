array=( '( a b c )' \
        '( 1 2 3 )' )

for elt in "${array[@]}";do
  l=$elt
  echo l=$l
  eval arr=$l
  echo ${arr[1]}
done

echo "array_len=${#array[*]}"
